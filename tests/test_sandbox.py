"""Sandbox（对话式沙盒模拟）测试 — 存储层 + 服务层，全 mock LLM。"""
from unittest.mock import MagicMock

import pytest

from brain_of_cloud.storage.sqlite import SQLiteStore


# ─────────────────────────── 存储层 ───────────────────────────

def _session_payload(session_id="sb_1", user_id="u1", status="active"):
    return {
        "session_id": session_id,
        "user_id": user_id,
        "mode": "scenario",
        "template_id": "t_guzhen_violation",
        "customer": {"name": "汉斯", "nationality": "德国", "age": 45},
        "state": {
            "stage": 0,
            "stage_turns": 1,
            "messages": [{"role": "customer", "content": "这地方怎么这么多规矩？"}],
        },
        "status": status,
        "score": None,
        "dims": None,
        "feedback": None,
        "created_at": "2026-08-19T00:00:00+00:00",
        "ended_at": None,
    }


def test_store_sandbox_session_roundtrip(tmp_path):
    store = SQLiteStore(tmp_path / "sandbox.sqlite")
    store.initialize()
    store.save_sandbox_session(_session_payload())

    loaded = store.get_sandbox_session("sb_1")
    assert loaded is not None
    assert loaded["user_id"] == "u1"
    assert loaded["mode"] == "scenario"
    assert loaded["customer"]["nationality"] == "德国"
    assert loaded["state"]["stage"] == 0
    assert len(loaded["state"]["messages"]) == 1


def test_store_sandbox_session_missing_returns_none(tmp_path):
    store = SQLiteStore(tmp_path / "sandbox.sqlite")
    store.initialize()
    assert store.get_sandbox_session("nope") is None


def test_store_sandbox_session_upsert_updates_row(tmp_path):
    store = SQLiteStore(tmp_path / "sandbox.sqlite")
    store.initialize()
    store.save_sandbox_session(_session_payload())

    updated = _session_payload()
    updated["state"]["stage"] = 1
    updated["score"] = 82
    updated["dims"] = [["表达能力", 4], ["控场能力", 4]]
    updated["feedback"] = {"strengths": ["安抚到位"]}
    store.save_sandbox_session(updated)

    loaded = store.get_sandbox_session("sb_1")
    assert loaded["state"]["stage"] == 1
    assert loaded["score"] == 82
    assert loaded["feedback"]["strengths"] == ["安抚到位"]


def test_store_list_sandbox_records_only_ended(tmp_path):
    store = SQLiteStore(tmp_path / "sandbox.sqlite")
    store.initialize()
    active = _session_payload("sb_active", "u1", status="active")
    ended1 = _session_payload("sb_e1", "u1", status="ended")
    ended1["score"] = 80
    ended1["ended_at"] = "2026-08-19T10:00:00+00:00"
    ended2 = _session_payload("sb_e2", "u1", status="ended")
    ended2["score"] = 90
    ended2["ended_at"] = "2026-08-19T11:00:00+00:00"
    store.save_sandbox_session(active)
    store.save_sandbox_session(ended1)
    store.save_sandbox_session(ended2)

    records = store.list_sandbox_records("u1")
    assert len(records) == 2
    assert all(r["status"] == "ended" for r in records)
    # 按时间倒序
    assert records[0]["session_id"] == "sb_e2"
    assert records[1]["session_id"] == "sb_e1"


# ─────────────────────────── 服务层（mock LLM） ───────────────────────────

from types import SimpleNamespace
from unittest.mock import MagicMock

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.sandbox import SandboxService


def _mock_llm(customer_reply=None, evaluation=None):
    """构造 mock LLM：customer 对话返回 reply JSON，评估返回 evaluation JSON。
    同时为子智能体（场景导演）提供 chat 通道（默认 continue，保持旧推进逻辑）。"""
    llm = MagicMock(spec=LLMClient)
    llm.model = "deepseek-chat"

    def _generate(system, user, **kwargs):
        if "评估师" in system:
            payload = evaluation or {
                "total": 86,
                "dims": {"表达能力": 4, "控场能力": 4, "文化知识": 5, "服务意识": 5, "互动引导": 3},
                "strengths": ["开场有吸引力", "讲解层次清晰"],
                "weaknesses": ["互动稍少"],
                "suggestions": ["多设计提问环节", "补充宗教文化细节"],
                "skill_keywords": ["导游服务规范", "讲解技巧"],
            }
        else:
            payload = customer_reply or {"reply": "好的，我听你的安排。", "mood": "满意", "advanced": False}
        import json
        return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))

    def _chat(messages, **kwargs):
        # 场景导演：默认 continue（不干预原推进逻辑）
        import json
        return SimpleNamespace(content=json.dumps(
            {"action": "continue", "reason": "剧情继续展开", "outcome": None}, ensure_ascii=False))

    llm.generate.side_effect = _generate
    llm.chat.side_effect = _chat
    return llm


def _make_service(tmp_path, llm=None, seed=42):
    store = SQLiteStore(tmp_path / "sandbox.sqlite")
    store.initialize()
    import random
    svc = SandboxService(llm_client=llm or _mock_llm(), store=store, rng=random.Random(seed))
    return svc


def test_sandbox_list_templates_and_mode_filter(tmp_path):
    svc = _make_service(tmp_path)
    all_t = svc.list_templates()
    assert len(all_t) >= 7
    assert {t["mode"] for t in all_t} == {"scenario", "narrate", "fullflow", "communication"}
    scenario = svc.list_templates(mode="scenario")
    assert all(t["mode"] == "scenario" for t in scenario)
    # 全流程分课已有单阶段、双阶段模板；每个场景都必须有可执行阶段。
    assert all(t["stage_count"] >= 1 for t in all_t)
    assert all(t["stage_count"] == 3 for t in all_t if t["mode"] == "communication")


def test_sandbox_get_template_unknown_raises(tmp_path):
    svc = _make_service(tmp_path)
    with pytest.raises(Exception, match="未知场景模板"):
        svc.get_template("nope")


def test_sandbox_start_session_random_customer_and_opening(tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    assert session["status"] == "active"
    assert session["user_id"] == "u1"
    assert session["template"]["title"] == "江南古镇 · 游客违规"
    assert session["customer"]["name"] in {"汉斯", "玛丽", "阿伦", "佐藤"}
    assert "hidden" not in session["customer"], "隐藏诉求不应暴露给学员"
    assert session["stage"]["index"] == 0
    msgs = session["messages"]
    assert msgs and msgs[0]["role"] == "customer"
    # 同种子随机性：不同 seed 可能抽到不同游客
    assert svc.start_session(user_id="u1", template_id="t_guzhen_violation")["session_id"] != session["session_id"]


def test_sandbox_start_session_opening_fallback_on_llm_failure(tmp_path):
    llm = _mock_llm()
    llm.generate.side_effect = RuntimeError("llm down")
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    assert session["messages"][0]["content"], "LLM 失败时应有兜底开场白"


def test_sandbox_send_message_stage_advance(tmp_path):
    llm = _mock_llm(customer_reply={"reply": "你说得对，我确实不该踩。", "mood": "一般", "advanced": True})
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]

    result = svc.send_message(sid, "先生您好，这里是文物保护区域，请您先出来，我来为您介绍这里的历史。")
    assert result["reply"] == "你说得对，我确实不该踩。"
    assert result["stage_advanced"] is True
    assert result["stage"] == 1  # 推进到第 2 阶段
    assert result["stage_tip"] is not None

    # 消息已持久化
    updated = svc.get_session(sid)
    roles = [m["role"] for m in updated["messages"]]
    assert roles == ["customer", "guide", "customer"]


def test_sandbox_send_message_no_auto_advance_without_goal(tmp_path):
    """修复：不再按固定轮数强制推进——目标未达成（advanced=False）时即使轮数达标也不推进。"""
    llm = _mock_llm(customer_reply={"reply": "嗯，我知道了。", "mood": "一般", "advanced": False, "trust_delta": 0})
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]

    # 第 1 阶段 min_turns=1：轮数已达标，但 advanced=False → 不推进（旧版会强制推进）
    r1 = svc.send_message(sid, "抱歉打扰，这里是古建筑保护区，请您先移步护栏外。")
    assert r1["stage"] == 0
    assert r1["stage_advanced"] is False

    # 再聊一轮仍不推进（剧情没演完）
    r2 = svc.send_message(sid, "吸烟区在前面，我陪您过去。")
    assert r2["stage"] == 0


def test_sandbox_send_message_last_stage_completes(tmp_path):
    llm = _mock_llm(customer_reply={"reply": "今天谢谢你，玩得很开心。", "mood": "满意", "advanced": True, "trust_delta": 5})
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    # 阶段 0（min_turns=1，advanced=True → 第 1 轮推进）
    # 阶段 1（min_turns=2，advanced=True → 第 2 轮才推进）
    # 阶段 2（min_turns=1，advanced=True → 完成）
    svc.send_message(sid, "欢迎来到古镇，请随我来。")
    svc.send_message(sid, "您看，这就是马头墙。")
    r_mid = svc.send_message(sid, "您看，这就是马头墙。")
    assert r_mid["stage"] == 2, "阶段 1 需要展开 2 轮才推进（最少展开轮数语义）"
    r = svc.send_message(sid, "感谢您的理解，希望您玩得愉快！")
    assert r["scene_complete"] is True
    assert r["stage"] == 2


def test_sandbox_send_message_on_ended_raises(tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    svc.end_session(sid, user_id="u1")
    with pytest.raises(Exception, match="已结束"):
        svc.send_message(sid, "还能继续吗？")


def test_sandbox_end_session_evaluates_and_persists(tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    svc.send_message(sid, "先生您好，这里是文物保护区域，请您先移步护栏外。")

    ended = svc.end_session(sid, user_id="u1")
    assert ended["status"] == "ended"
    assert ended["score"] == 86
    assert ended["dims"]["表达能力"] == 4
    assert ended["feedback"]["suggestions"]
    assert ended["feedback"]["recommended_skills"], "应关联到知识库技能点"

    # 落为学习中心报告资产
    assets = svc._store.get_assets("u1", asset_type="report")
    assert assets, "评估报告应落库为资产"
    assert "沙盒评估" in assets[0]["title"]


def test_sandbox_end_session_idempotent(tmp_path):
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    svc.send_message(sid, "请先不要踩踏护栏。")
    first = svc.end_session(sid, user_id="u1")
    # 二次调用返回既有结果，不重复评估
    second = svc.end_session(sid, user_id="u1")
    assert second["score"] == first["score"]
    assert second["feedback"] == first["feedback"]


def test_sandbox_end_session_llm_failure_falls_back(tmp_path):
    llm = _mock_llm()
    llm.generate.side_effect = RuntimeError("llm down")
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    svc.send_message(sid, "请勿踩踏。")
    ended = svc.end_session(sid, user_id="u1")
    assert ended["status"] == "ended"
    assert 0 <= ended["score"] <= 100


def test_sandbox_list_user_records(tmp_path):
    svc = _make_service(tmp_path)
    s1 = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    svc.send_message(s1["session_id"], "请勿踩踏护栏。")
    svc.end_session(s1["session_id"], user_id="u1")
    s2 = svc.start_session(user_id="u1", template_id="t_restaurant_etiquette")
    svc.send_message(s2["session_id"], "请各位按主宾顺序入座。")
    svc.end_session(s2["session_id"], user_id="u1")

    records = svc.list_user_records("u1")
    assert len(records) == 2
    assert all(r["score"] is not None for r in records)
    titles = {r["title"] for r in records}
    assert "江南古镇 · 游客违规" in titles
    assert "法式餐厅 · 用餐礼仪" in titles


def test_sandbox_get_session_unknown_raises(tmp_path):
    svc = _make_service(tmp_path)
    with pytest.raises(Exception, match="未知沙盒会话"):
        svc.get_session("nope")


# ─────────────────────────── 完整情景模拟器（v2） ───────────────────────────

def test_sandbox_customer_state_initialized(tmp_path):
    """游客心理状态初始化：信任度在合理区间、情绪一般。"""
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    cs = session["customer_state"]
    assert 0 <= cs["trust"] <= 100
    assert cs["mood"] in ("满意", "一般", "不满", "愤怒")
    assert cs["hidden_revealed"] is False


def test_sandbox_trust_changes_with_delta(tmp_path):
    """游客信任度随 trust_delta 累积变化（模拟角色连续反应）。"""
    llm = _mock_llm(customer_reply={
        "reply": "谢谢你解释，我理解了。", "mood": "满意",
        "trust_delta": 10, "reaction": "导游解释得很清楚", "advanced": False,
    })
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    before = session["customer_state"]["trust"]

    r1 = svc.send_message(sid, "这里的历史确实值得保护。")
    assert r1["trust"] == min(100, before + 10)

    r2 = svc.send_message(sid, "我再给您讲讲这座桥的故事。")
    assert r2["trust"] == min(100, before + 20)


def test_sandbox_trust_never_out_of_range(tmp_path):
    """信任度钳制在 0-100（连续大额加减不越界）。"""
    llm = _mock_llm(customer_reply={"reply": "哼。", "mood": "愤怒", "trust_delta": -15, "advanced": False})
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    for _ in range(8):
        r = svc.send_message(sid, "您先别激动……")
    assert 0 <= r["trust"] <= 100


def test_sandbox_tension_event_on_low_trust(tmp_path):
    """信任崩塌 → 剧情压力事件（游客威胁投诉），化解前不推进阶段。"""
    llm = _mock_llm(customer_reply={"reply": "我要投诉你们！", "mood": "愤怒", "trust_delta": -15, "advanced": False})
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    # 连续施压直到信任 < 30 且连续不满 ≥ 2
    for _ in range(6):
        r = svc.send_message(sid, "您别这样……")
        if r["tension"]:
            break
    assert r["tension"] is True
    assert r["stage"] == 0, "压力事件中阶段不推进"
    tip = r["stage_tip"]
    assert tip is not None and tip.get("type") == "tension"


def test_sandbox_tension_resolved_when_trust_recovers(tmp_path):
    """压力事件中信任回升到 40 → 事件化解，游客继续配合。"""
    replies = iter([
        {"reply": "这地方规矩真多。", "mood": "一般", "trust_delta": 0, "advanced": False},  # 开场白
        {"reply": "哼！", "mood": "愤怒", "trust_delta": -20, "advanced": False},            # 施压1：count=1
        {"reply": "我要投诉你们！", "mood": "愤怒", "trust_delta": -20, "advanced": False},  # 施压2：count=2 且 trust<30 → 触发
        {"reply": "好吧……我信你一次。", "mood": "一般", "trust_delta": 30, "advanced": False},  # 化解（trust 回升 ≥40）
    ])
    llm = MagicMock(spec=LLMClient)
    llm.model = "deepseek-chat"
    import json as _json
    def _gen(system, user, **kwargs):
        payload = next(replies, {"reply": "嗯。", "mood": "一般", "trust_delta": 0, "advanced": False})
        return SimpleNamespace(content=_json.dumps(payload, ensure_ascii=False))
    def _chat(messages, **kwargs):
        # 场景导演：continue，不干预压力事件化解逻辑
        return SimpleNamespace(content=_json.dumps(
            {"action": "continue", "reason": "继续", "outcome": None}, ensure_ascii=False))
    llm.generate.side_effect = _gen
    llm.chat.side_effect = _chat
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]

    r0 = svc.send_message(sid, "请您冷静。")
    assert r0["tension"] is False, "第一轮不满不触发事件"
    r1 = svc.send_message(sid, "您先听我解释。")
    assert r1["tension"] is True, "信任崩塌后触发压力事件"
    assert r1["stage"] == 0, "压力事件中阶段不推进"
    r2 = svc.send_message(sid, "我真诚道歉，并承诺给您补偿。")
    assert r2["tension"] is False, "信任回升后事件化解"
    assert r2["stage_tip"]["type"] == "tension_resolved"


def test_sandbox_max_turns_timeout_advances(tmp_path):
    """防呆上限：阶段轮数超过 max_turns 仍无进展 → 带提示强制收束（非固定轮数）。"""
    llm = _mock_llm(customer_reply={"reply": "嗯。", "mood": "一般", "trust_delta": 0, "advanced": False})
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    # 阶段 0 min_turns=1 max_turns=8：聊到第 8 轮仍无进展 → timeout 推进
    r = None
    for _ in range(8):
        r = svc.send_message(sid, "您先听我说完……")
    assert r["stage"] == 1
    assert r["stage_tip"]["type"] == "timeout"


def test_sandbox_hidden_revealed_state(tmp_path):
    """游客隐藏诉求流露 → customer_state.hidden_revealed 更新且对外可见。"""
    llm = _mock_llm(customer_reply={
        "reply": "其实我担心的是后面的行程会不会缩水……", "mood": "一般",
        "trust_delta": 5, "hidden_revealed": True, "advanced": False,
    })
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]

    r = svc.send_message(sid, "有什么顾虑您都可以跟我说。")

    assert r["hidden_revealed"] is True
    updated = svc.get_session(sid)
    assert updated["customer_state"]["hidden_revealed"] is True
    # 隐藏诉求原文仍不对学员暴露
    assert "hidden" not in updated["customer"]


def test_sandbox_prompt_includes_psych_state_and_memory(tmp_path):
    """游客 prompt 包含心理状态（信任/情绪/疑虑）与连续记忆。"""
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    svc.send_message(sid, "先生您好，这里是文物保护区域。")

    calls = svc._llm.generate.call_args_list
    last_system = str(calls[-1].args[0])
    assert "信任度" in last_system
    assert "当前情绪" in last_system
    assert "你的记忆" in last_system or "你的心理状态" in last_system


def test_sandbox_prompt_one_on_one_principle(tmp_path):
    """游客 prompt 含一对一原则：禁止提及/指派处理其他游客（修复出戏问题）。"""
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    svc.send_message(sid, "先生，请您先移步护栏外。")

    calls = svc._llm.generate.call_args_list
    last_system = str(calls[-1].args[0])
    assert "一对一原则" in last_system
    assert "禁止提及" in last_system and "其他游客" in last_system
    assert "你自己的行为" in last_system


def test_sandbox_templates_third_party_situations_are_self(tmp_path):
    """三个冲突模板的 situation 均为游客本人行为（违规/座次/拍照者 = 扮演游客自己）。"""
    svc = _make_service(tmp_path)
    t1 = svc.get_template("t_guzhen_violation")
    t2 = svc.get_template("t_restaurant_etiquette")
    t3 = svc.get_template("t_temple_taboo")
    assert "你刚跨进护栏" in t1.situation
    assert "你对座次安排不满" in t2.situation
    assert "你正对着佛像举起手机" in t3.situation
    # 模板 opening 不再出现「一位游客/两位游客」第三方违规者描述
    assert "一位游客正跨进" not in t1.opening
    assert "两位游客" not in t2.opening
    assert "一位游客正准备" not in t3.opening
