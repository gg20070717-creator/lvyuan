"""教学会话状态机 + 上下文感知出题（一对一教学闭环）测试。"""
import json
from unittest.mock import MagicMock

import pytest

from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.services.teaching import (
    DIFFICULTY_ORDER,
    TeachingStateService,
)
from brain_of_cloud.storage.sqlite import SQLiteStore


def _make_mock_llm():
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    return llm


# ───────────────────── 状态机基础 ─────────────────────

def test_get_or_create_defaults(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)

    state = svc.get_or_create("s1", "u1")

    assert state["stage"] == "goal_setting"
    assert state["topic_ids"] == []
    assert state["depth"] == "intro"
    assert state["consecutive_correct"] == 0
    assert state["consecutive_incorrect"] == 0
    # 持久化后可重新读回
    again = svc.get_or_create("s1", "u1")
    assert again["session_id"] == "s1"


def test_set_topic_enters_teaching_and_resets(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)

    svc.transit("s1", "u1", "practicing")
    svc.record_answer("s1", "u1", "q1", False)
    svc.record_answer("s1", "u1", "q1", True)

    state = svc.set_topic("s1", "u1", ["kp_welcome"])

    assert state["stage"] == "teaching"
    assert state["topic_ids"] == ["kp_welcome"]
    assert state["quiz_history"] == []
    assert state["consecutive_correct"] == 0
    assert state["consecutive_incorrect"] == 0


def test_transit_rejects_invalid_stage(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)
    with pytest.raises(ValueError):
        svc.transit("s1", "u1", "not_a_stage")


def test_record_quiz_tracks_history_and_last_quiz(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)

    state = svc.record_quiz(
        "s1", "u1", "q1",
        question_info={"question_id": "q1", "prompt": "题目?", "options": ["A. 1", "B. 2"]},
        difficulty="basic",
    )

    assert state["stage"] == "practicing"
    assert state["quiz_history"] == ["q1"]
    assert state["depth"] == "basic"
    assert state["last_quiz"]["question_id"] == "q1"
    # 重复出同一题不重复记录
    state = svc.record_quiz("s1", "u1", "q1", difficulty="basic")
    assert state["quiz_history"] == ["q1"]


def test_record_answer_transitions_and_actions(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)
    svc.set_topic("s1", "u1", ["kp_welcome"])

    # 答错 → reteach，连续错误累计
    s = svc.record_answer("s1", "u1", "q1", False)
    assert s["stage"] == "feedback"
    assert s["consecutive_incorrect"] == 1
    assert s["consecutive_correct"] == 0

    # 答对 → extend
    s = svc.record_answer("s1", "u1", "q2", True)
    assert s["consecutive_correct"] == 1
    assert s["consecutive_incorrect"] == 0

    # 连续答对 3 次 → 升难度（intro → basic），计数归零
    s = svc.record_answer("s1", "u1", "q3", True)
    s = svc.record_answer("s1", "u1", "q4", True)
    assert s["depth"] == "basic"
    assert s["consecutive_correct"] == 0


def test_three_wrong_downgrades_depth(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)
    svc.set_topic("s1", "u1", ["kp_welcome"], depth="advanced")

    svc.record_answer("s1", "u1", "q1", False)
    svc.record_answer("s1", "u1", "q2", False)
    s = svc.record_answer("s1", "u1", "q3", False)

    assert s["depth"] == "basic"  # advanced → 降一档
    assert s["consecutive_incorrect"] == 0


def test_decide_difficulty_adapts_to_mastery(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)
    state = svc.get_or_create("s1", "u1")

    assert svc.decide_difficulty(state, None) == "intro"       # 未学过 → 保持
    assert svc.decide_difficulty(state, 0.9) == "basic"        # 掌握度高 → 升档
    state["depth"] = "basic"
    assert svc.decide_difficulty(state, 0.5) == "intro"        # 掌握度低 → 降档
    assert svc.decide_difficulty(state, 0.7) == "basic"        # 中间 → 保持
    state["depth"] = "comprehensive"
    assert svc.decide_difficulty(state, 1.0) == "comprehensive"  # 封顶


# ───────────────────── 出题硬校验（orchestrator） ─────────────────────

def _orchestrator(tmp_path):
    store = SQLiteStore(tmp_path / "o.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orch._user_id_ctx.set("user_1")
    orch._session_id_ctx.set("session_1")
    return orch, store


def test_quiz_without_topic_rejected(tmp_path):
    """无教学主题 + 非随机模式 → 拒绝出题（教学铁律 2 硬校验）。"""
    orch, _ = _orchestrator(tmp_path)

    payload = json.loads(orch._handle_quiz_user())

    assert payload["error"] == "no_active_topic"
    assert "讲解" in payload["message"]


def test_quiz_injects_topic_from_teaching_state(tmp_path):
    """教学状态锁定主题后，出题自动注入主题并进入练习阶段。"""
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])

    payload = json.loads(orch._handle_quiz_user())

    assert payload["question_id"] == "q_welcome_1"
    assert payload["knowledge_point_title"]  # 主题标题已解析
    assert payload["teaching"]["stage"] == "practicing"
    assert payload["teaching"]["last_quiz"]["question_id"] == "q_welcome_1"


def test_quiz_explicit_random_without_topic_allowed(tmp_path):
    """学员明确要求随机（random_mode=explicit）→ 允许出题。"""
    orch, _ = _orchestrator(tmp_path)

    payload = json.loads(orch._handle_quiz_user(random_mode="explicit"))

    assert "error" not in payload
    assert payload["question_id"]


def test_quiz_avoids_repeat_questions(tmp_path):
    """同一主题已出过的题不再重复（单题技能点池耗尽 → 明确提示）。"""
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])

    first = json.loads(orch._handle_quiz_user())
    assert first["question_id"] == "q_welcome_1"

    second = json.loads(orch._handle_quiz_user())
    assert second["question_id"] == ""  # 已出过的题不再重复
    assert "暂无" in second["message"]


def test_quiz_difficulty_drops_after_consecutive_wrong(tmp_path):
    """连续答错后出题难度下降（context-aware 难度）。"""
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"], depth="basic")
    orch._teaching.record_answer("session_1", "user_1", "q_welcome_1", False)
    orch._teaching.record_answer("session_1", "user_1", "q_welcome_1", False)
    orch._teaching.record_answer("session_1", "user_1", "q_welcome_1", False)  # 3 连错 → 降档

    payload = json.loads(orch._handle_quiz_user())

    assert payload["question_id"] == "q_welcome_1"  # 降回 intro 档，题目可出
    assert payload["teaching"]["depth"] == "intro"


def test_submit_answer_wrong_returns_reteach_hint(tmp_path):
    """答错 → reteach_hint.need_reteach=True + 错因角度（阅卷老师生成）。"""
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])
    orch._analyzer.reteach_angle = MagicMock(return_value="用「先报告后安抚」的顺序反讲")

    payload = json.loads(orch._handle_submit_answer("q_welcome_1", "不知道"))

    assert payload["correct"] is False
    assert payload["reteach_hint"]["need_reteach"] is True
    assert payload["reteach_hint"]["next_action"] == "reteach"
    assert "顺序反讲" in payload["reteach_hint"]["angle"]
    assert payload["teaching"]["stage"] == "feedback"


def test_submit_answer_correct_returns_extend(tmp_path):
    """答对 → need_reteach=False，next_action=extend（补延伸考点）。"""
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])

    good = "I welcome the tourists. As the local guide I introduce the driver " \
           "and explain the itinerary with meeting time and safety reminders."
    payload = json.loads(orch._handle_submit_answer("q_welcome_1", good))

    assert payload["correct"] is True
    assert payload["reteach_hint"]["need_reteach"] is False
    assert payload["reteach_hint"]["next_action"] == "extend"


def test_end_to_end_teaching_loop(tmp_path):
    """完整闭环：出题 → 答错 → 判分反馈（管家循环内注入纠错指令）。"""
    from brain_of_cloud.services.agents.concierge import AgentResponse
    orch, store = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])
    orch._analyzer.reteach_angle = MagicMock(return_value="换个角度讲")

    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    calls = [0]

    def think(conversation, tools=None):
        calls[0] += 1
        if calls[0] == 1:
            return AgentResponse(
                text="来考你一道题。",
                tool_calls=[{"id": "t1", "name": "quiz_user",
                             "arguments": {"knowledge_point_ids": ["kp_welcome"]}}],
            )
        if calls[0] == 2:
            return AgentResponse(
                text="请作答。",
                tool_calls=[{"id": "t2", "name": "submit_answer",
                             "arguments": {"question_id": "q_welcome_1", "answer": "不知道"}}],
            )
        if calls[0] == 3:
            return AgentResponse(
                text="答错了，我换个角度重新讲：欢迎词要先问候再介绍自己……",
                tool_calls=[{"id": "t3", "name": "quiz_user",
                             "arguments": {"knowledge_point_ids": ["kp_welcome"]}}],
            )
        return AgentResponse(text="再来一道题：……")

    mc.think.side_effect = think
    orch._concierge = mc

    result = orch.handle_user_message("user_1", "session_1", "讲讲欢迎词怎么写")

    assert result.tool_calls_made == ["quiz_user", "submit_answer", "quiz_user"]
    assert result.teaching is not None
    # 小插件题库 kp 内单题时重出题池耗尽 → 阶段停在 feedback；713 题真实库会回到 practicing
    assert result.teaching["stage"] in ("feedback", "practicing")
    # 纠错讲解文本未被工具轮吞掉：最终回复包含重讲内容（教学铁律 4 的 UX 保证）
    assert "换个角度重新讲" in result.response
    # 循环中注入了纠错教学系统指令（强制重讲）
    assert any(
        isinstance(m, dict) and m.get("role") == "system" and "纠错" in m.get("content", "")
        for m in orch._sessions["session_1"]
    )


def test_search_knowledge_auto_locks_topic(tmp_path):
    """首次检索（无主题）→ 用证据技能点自动锁定教学主题。"""
    from types import SimpleNamespace
    from brain_of_cloud.domain.models import Evidence
    orch, _ = _orchestrator(tmp_path)
    orch._retrieval.run = MagicMock(
        return_value=SimpleNamespace(
            query="构景手法",
            evidence=[
                Evidence(
                    chunk_id="kp_borrow", content="借景…", source="教材",
                    trust_score=0.9, knowledge_point_ids=["kp_borrow"],
                ),
            ],
        )
    )

    payload = json.loads(orch._handle_search_knowledge("中国古典园林的构景手法"))

    state = orch._teaching.get_or_create("session_1", "user_1")
    assert state["topic_ids"] == ["kp_borrow"]
    assert state["stage"] == "teaching"
    assert payload["teaching"]["topics"][0]["id"] == "kp_borrow"
    # 检索结果带技能点 ID（供管家 set_teaching_topic / quiz_user 使用）
    assert payload["results"][0]["knowledge_point_ids"] == ["kp_borrow"]


def test_search_does_not_override_existing_topic(tmp_path):
    """已有主题时，后续检索不覆盖当前教学主题。"""
    from types import SimpleNamespace
    from brain_of_cloud.domain.models import Evidence
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])
    orch._retrieval.run = MagicMock(
        return_value=SimpleNamespace(
            query="别的",
            evidence=[
                Evidence(
                    chunk_id="kp_other", content="其他…", source="教材",
                    trust_score=0.9, knowledge_point_ids=["kp_other"],
                ),
            ],
        )
    )

    orch._handle_search_knowledge("随便查查")

    state = orch._teaching.get_or_create("session_1", "user_1")
    assert state["topic_ids"] == ["kp_welcome"]


def test_set_teaching_topic_switches_topic(tmp_path):
    """显式切换教学主题（学员换主题时管家调用）。"""
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])

    payload = json.loads(orch._handle_set_teaching_topic(["kp_emergency"]))

    assert payload["ok"] is True
    assert payload["topic_titles"]
    state = orch._teaching.get_or_create("session_1", "user_1")
    assert state["topic_ids"] == ["kp_emergency"]
    assert state["stage"] == "teaching"

    err = json.loads(orch._handle_set_teaching_topic())
    assert err["error"] == "missing_knowledge_point_ids"


def test_teaching_state_deleted_with_user_data(tmp_path):
    """删除用户数据时教学状态一并清除（数据合规）。"""
    store = SQLiteStore(tmp_path / "c.sqlite")
    store.initialize()
    svc = TeachingStateService(store)
    svc.set_topic("s1", "u1", ["kp_welcome"])

    store.delete_user_data("u1", InboundGuidePlugin().manifest["plugin_id"])

    assert store.get_teaching_state("s1") is None


# ───────────────────── T6 persona：教学上下文注入 ─────────────────────

def test_user_context_injects_teaching_state_when_topic_locked(tmp_path):
    """教学主题锁定后，管家上下文注入当前教学信息（像老师接着上课，上下文可见）。"""
    orch, _ = _orchestrator(tmp_path)
    orch._teaching.set_topic("session_1", "user_1", ["kp_welcome"])
    state = orch._teaching.get_or_create("session_1", "user_1")
    state["stage"] = "practicing"
    state["consecutive_incorrect"] = 2
    orch._teaching.save(state)

    ctx = orch._build_user_context("user_1")

    assert "当前教学上下文" in ctx
    assert "这堂课的主题" in ctx
    assert "正在练习" in ctx            # 阶段中文说明
    assert "连续答对 0 题、连续答错 2 题" in ctx
    assert "接着上节课往下讲" in ctx      # 自然衔接指令


def test_user_context_no_teaching_block_when_no_topic(tmp_path):
    """无教学主题时不注入教学上下文块（避免打扰普通对话）。"""
    orch, _ = _orchestrator(tmp_path)

    ctx = orch._build_user_context("user_1")

    assert "当前教学上下文" not in ctx


def test_reteach_begin_finish_roundtrip(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)

    qinfo = {"question_id": "q_wrong", "prompt": "题目?", "options": ["A. 1", "B. 2"], "difficulty_level": 2}
    svc.begin_reteach("s1", "u1", qinfo)
    state = svc.get_or_create("s1", "u1")
    assert state["reteach_question_id"] == "q_wrong"
    assert state["reteach_question"]["question_id"] == "q_wrong"

    # 答对收口：解除的正是该题 → True，且标记清空
    assert svc.finish_reteach("s1", "u1", "q_wrong") is True
    state = svc.get_or_create("s1", "u1")
    assert state["reteach_question_id"] is None
    assert state["reteach_question"] is None


def test_finish_reteach_clears_stale_and_set_topic_resets(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    svc = TeachingStateService(store)

    svc.begin_reteach("s1", "u1", {"question_id": "q1", "prompt": "p1"})
    # 学员答的是别的题（陈旧纠错态）→ 也会清除，返回 False
    assert svc.finish_reteach("s1", "u1", "q_other") is False
    state = svc.get_or_create("s1", "u1")
    assert state["reteach_question_id"] is None

    svc.begin_reteach("s1", "u1", {"question_id": "q1", "prompt": "p1"})
    svc.set_topic("s1", "u1", ["kp_welcome"])
    state = svc.get_or_create("s1", "u1")
    assert state["reteach_question_id"] is None
    assert state["reteach_question"] is None
