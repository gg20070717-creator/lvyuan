"""沙盒 v3 集成测试：场景库/场景导演/游客生成/评估增强（mock LLM）。"""
import json
import random
from types import SimpleNamespace
from unittest.mock import MagicMock

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.sandbox import SandboxService


def _mock_llm():
    """mock LLM：generate（游客对话/评估）与 chat（子智能体：导演/游客生成/评估）双通道。"""
    llm = MagicMock(spec=LLMClient)
    llm.model = "deepseek-chat"

    def _dispatch(system, user, **kwargs):
        if "评估师" in system:
            return {
                "total": 70,
                "dims": {"表达能力": 3, "控场能力": 3, "文化知识": 3, "服务意识": 4, "互动引导": 3},
                "strengths": ["保持了服务态度"],
                "weaknesses": ["未能化解冲突"],
                "suggestions": ["先共情再讲规则"],
                "skill_keywords": ["导游服务规范"],
            }
        if "导演" in system:
            return {"action": "continue", "reason": "剧情仍在展开", "outcome": None}
        if "游客人设设计师" in system:
            import re as _re
            m = _re.search(r"具体年龄为 (\d+) 岁", user or "")
            age = m.group(1) if m else "30"
            return {
                "name": "小林", "nationality": "中国", "age": age,
                "personality": "外向活泼", "preferences": "爱拍照",
                "quirks": "语速快", "hidden": "想多拍打卡照",
                "gender": "男", "occupation": "大学生", "health": "良好",
                "consumption": "预算敏感", "speech_style": "爱用网络词",
            }
        return {"reply": "好的，听你的。", "mood": "一般", "advanced": True, "trust_delta": 0}

    def _gen(system, user, **kwargs):
        return SimpleNamespace(content=json.dumps(_dispatch(system, user, **kwargs), ensure_ascii=False))

    def _chat(messages, **kwargs):
        system = kwargs.pop("system", "")
        user = messages[0]["content"] if messages else ""
        return _gen(system, user, **kwargs)

    llm.chat.side_effect = _chat
    llm.generate.side_effect = _gen
    return llm


def _make_service(tmp_path, llm=None):
    from brain_of_cloud.storage.sqlite import SQLiteStore
    store = SQLiteStore(tmp_path / "sandbox_v3.sqlite")
    store.initialize()
    return SandboxService(llm_client=llm or _mock_llm(), store=store, rng=random.Random(7))


# ── 场景库（t1） ──

def test_template_library_has_20_plus_scenes(tmp_path):
    from brain_of_cloud.services.sandbox_templates import TEMPLATES, TEMPLATE_CATEGORIES
    assert len(TEMPLATES) >= 20, f"场景数不足 20: {len(TEMPLATES)}"
    ids = [t.template_id for t in TEMPLATES]
    assert len(ids) == len(set(ids)), "template_id 重复"
    # 原 7 个 id 保留
    for old in ("t_guzhen_violation", "t_restaurant_etiquette", "t_airport_delay",
                "t_temple_taboo", "t_yungang", "t_guzhen_narrate", "t_ff_pre_trip"):
        assert old in ids, f"原场景缺失: {old}"
    assert TEMPLATE_CATEGORIES, "分类说明缺失"
    # 三种模式齐全
    modes = {t.mode for t in TEMPLATES}
    assert modes == {"scenario", "narrate", "fullflow"}


def test_service_lists_20_plus_templates(tmp_path):
    svc = _make_service(tmp_path)
    all_t = svc.list_templates()
    assert len(all_t) >= 20
    scenario = svc.list_templates(mode="scenario")
    assert len(scenario) >= 10, "情景模拟场景应 ≥10"


# ── 游客动态生成（t3） ──

def test_start_session_generates_customer_with_new_dims(tmp_path):
    """start_session 用生成器：游客含新维度字段且 hidden 不外泄。"""
    svc = _make_service(tmp_path)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    c = session["customer"]
    assert c["name"]
    assert "hidden" not in c, "隐藏诉求不应暴露"
    # 新维度字段存在（mock 返回了）
    for k in ("gender", "occupation", "health", "consumption", "speech_style"):
        assert k in c, f"游客缺维度: {k}"
    assert int(c["age"]) > 0, "年龄应为有效数字"


def test_start_session_fallback_when_llm_down(tmp_path):
    """LLM 挂掉 → 兜底模板游客池，不抛异常。"""
    llm = _mock_llm()
    llm.generate.side_effect = RuntimeError("llm down")
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    assert session["customer"]["name"], "应有兜底游客"
    assert session["messages"][0]["content"]


def test_customer_age_bands_diverse():
    """5 个年龄段各生成一个年龄，覆盖青年到老年。"""
    from brain_of_cloud.services.customer_generator import AGE_BANDS, CustomerGenerator
    llm = _mock_llm()
    gen = CustomerGenerator(llm)
    rng = random.Random(1)
    for band, _desc in AGE_BANDS:
        if band == "70+":
            lo, hi = 70, 85
        else:
            lo, hi = (int(x) for x in band.split("-"))
        data = gen.generate(None, rng, band=band)  # type: ignore[arg-type]
        age = int(data["age"])
        assert lo <= age <= hi, f"{band} 生成的年龄 {age} 越界"
    # 均匀分布抽查
    seen = set()
    for _ in range(200):
        seen.add(gen.pick_age_band(random.Random()))
    assert len(seen) >= 3, "pick_age_band 分布不够多样"


# ── 场景导演（t2） ──

def _wire_llm(llm, dispatcher):
    """把 dispatcher(system, user, **kwargs) -> payload 同时接到 generate 与 chat 通道。"""
    import json as _json

    def _gen(system, user, **kwargs):
        return SimpleNamespace(content=_json.dumps(dispatcher(system, user, **kwargs), ensure_ascii=False))

    def _chat(messages, **kwargs):
        system = kwargs.pop("system", "")
        user = messages[0]["content"] if messages else ""
        return _gen(system, user, **kwargs)

    llm.generate.side_effect = _gen
    llm.chat.side_effect = _chat


def test_send_message_scene_fail_sets_outcome(tmp_path):
    """导演判定 fail → scene_outcome=failed + 场景终止。"""
    llm = _mock_llm()
    calls = {"n": 0}

    def _dispatcher(system, user, **kwargs):
        calls["n"] += 1
        if "导演" in system:
            return {"action": "fail", "reason": "游客信任崩塌，明确表示要离团投诉",
                    "outcome": "failed"}
        if "评估师" in system:
            return {"total": 40, "dims": {"表达能力": 2, "控场能力": 2, "文化知识": 2,
                                           "服务意识": 2, "互动引导": 2},
                    "strengths": [], "weaknesses": ["冲突升级"], "suggestions": ["复盘共情"],
                    "skill_keywords": ["导游服务规范"]}
        return {"reply": "我受够了，我要投诉！", "mood": "愤怒", "advanced": False,
                "trust_delta": -30}

    _wire_llm(llm, _dispatcher)
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    result = svc.send_message(sid, "先生，规则就是规则。")
    assert result["scene_outcome"] == "failed"
    assert result["scene_fail_reason"]
    ended = svc.end_session(sid, user_id="u1")
    assert ended["scene_outcome"] == "failed"
    assert ended["score"] == 40


def test_send_message_scene_complete_sets_outcome(tmp_path):
    """导演判定 complete（最后阶段）→ scene_outcome=success。"""
    llm = _mock_llm()

    def _dispatcher(system, user, **kwargs):
        if "导演" in system:
            if "是否为最后阶段：是" in user:
                return {"action": "complete", "reason": "所有阶段目标达成", "outcome": "success"}
            return {"action": "advance", "reason": "本阶段目标达成", "outcome": None}
        if "评估师" in system:
            return {"total": 90, "dims": {d: 5 for d in ("表达能力", "控场能力", "文化知识", "服务意识", "互动引导")},
                    "strengths": ["处理得当"], "weaknesses": [], "suggestions": ["保持"],
                    "skill_keywords": ["导游服务规范"]}
        return {"reply": "谢谢你的照顾！", "mood": "满意", "advanced": True, "trust_delta": 5}

    _wire_llm(llm, _dispatcher)
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    # 3 个阶段：导演每轮 advance，直到最后阶段 complete
    result = None
    for _ in range(4):
        result = svc.send_message(sid, "感谢您的配合，祝您玩得开心！")
        if result.get("scene_complete"):
            break
    assert result["scene_complete"] is True
    assert result["scene_outcome"] == "success"


def test_director_continue_keeps_existing_advance_logic(tmp_path):
    """导演 continue（或 LLM 失败）→ 沿用原有 advanced 阶段推进逻辑（回归兼容）。"""
    llm = _mock_llm()  # 导演返回 continue
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    result = svc.send_message(sid, "先生您好，这里是文物保护区域，请您先移步护栏外。")
    # mock 游客 advanced=True 且 min_turns=1 → 阶段推进（导演 continue 不拦截）
    assert result["stage_advanced"] is True
    assert result["scene_outcome"] is None


# ── 评估增强（t5） ──

def test_end_session_evaluation_includes_scene_outcome(tmp_path):
    """结算评估注入场景结果与信任轨迹。"""
    captured = {}

    def _dispatcher(system, user, **kwargs):
        if "评估师" in system:
            captured["user_prompt"] = user
            return {
                "total": 75,
                "dims": {d: 3 for d in ("表达能力", "控场能力", "文化知识", "服务意识", "互动引导")},
                "strengths": ["有服务意识"], "weaknesses": ["讲解不足"],
                "suggestions": ["加强文化知识"], "skill_keywords": ["讲解技巧"],
            }
        if "导演" in system:
            return {"action": "continue", "reason": "继续", "outcome": None}
        return {"reply": "好的。", "mood": "一般", "advanced": False, "trust_delta": 0}

    llm = MagicMock(spec=LLMClient)
    llm.model = "deepseek-chat"
    _wire_llm(llm, _dispatcher)
    svc = _make_service(tmp_path, llm=llm)
    session = svc.start_session(user_id="u1", template_id="t_guzhen_violation")
    sid = session["session_id"]
    svc.send_message(sid, "请勿踩踏护栏。")
    ended = svc.end_session(sid, user_id="u1")
    assert ended["status"] == "ended"
    assert ended["score"] == 75
    # 评估 prompt 包含场景信息（游客/信任/阶段）
    assert "游客" in captured["user_prompt"]
    assert "信任" in captured["user_prompt"]
    assert "阶段" in captured["user_prompt"]
