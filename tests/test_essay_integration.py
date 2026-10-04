"""进阶教学闭环集成测试：quiz_user 进度/exhausted、generate_essay_question、submit_answer(essay)。

两类测试：
- handler 直调：验证工具返回 JSON 结构（progress/exhausted/essay_ready/error）
- 完整流程：mock 管家走 handle_user_message，验证工具链打通、teaching 状态、submissions 落库
"""
import json
from unittest.mock import MagicMock

from brain_of_cloud.domain.models import TaskStatus
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def _make_mock_llm():
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    return llm


def _canned_concierge(plan):
    """Concierge mock：第 1 次调用触发 plan(calls)，之后直接回复文本。"""
    from brain_of_cloud.services.agents.concierge import AgentResponse
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    state = {"n": 0}
    def think(conversation, tools=None):
        state["n"] += 1
        if state["n"] == 1:
            return AgentResponse(text="好的，我来处理。", tool_calls=plan())
        return AgentResponse(text="题目已出，请作答。")
    mc.think.side_effect = think
    return mc


def _orchestrator(tmp_path):
    store = SQLiteStore(tmp_path / "essay.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")
    return orch


# ═══════════════ handler 直调：返回 JSON 结构 ═══════════════

def test_quiz_user_handler_returns_type_and_progress():
    """quiz_user 返回 type=choice + progress {done,total,exhausted}（前端渲染依据）。"""
    orch = _orchestrator(MagicMock())  # 不走 store，直接测 handler
    orch._teaching.set_topic("s1", "u1", ["kp_welcome"])
    payload = json.loads(orch._handle_quiz_user(knowledge_point_ids=["kp_welcome"]))
    assert payload.get("type") == "choice"
    assert "question" in payload
    assert "progress" in payload
    assert set(payload["progress"].keys()) == {"done", "total", "exhausted"}


def test_quiz_user_exhausted_returns_essay_ready(tmp_path):
    """主题选择题全部做完 → quiz_user 返回 essay_ready 信号引导进阶简答题。"""
    from brain_of_cloud.domain.models import Question
    from brain_of_cloud.plugins import InboundGuidePlugin

    class _ChoicePlugin(InboundGuidePlugin):
        """带 2 道选择题的假插件（绑定同一技能点）。"""
        def __init__(self) -> None:
            super().__init__()
            self._questions = [
                Question(
                    question_id="c1", knowledge_point_id="kp_choice", difficulty="basic",
                    prompt="一五计划的起止时间是？",
                    options=["A. 1950～1954", "B. 1953～1957", "C. 1956～1960", "D. 1958～1962"],
                    answer="B", explanation="1953～1957 年。",
                ),
                Question(
                    question_id="c2", knowledge_point_id="kp_choice", difficulty="basic",
                    prompt="一五计划期间的重点是？",
                    options=["A. 轻工业", "B. 重工业", "C. 农业", "D. 服务业"],
                    answer="B", explanation="优先发展重工业。",
                ),
            ]

    store = SQLiteStore(tmp_path / "essay_ex.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=_ChoicePlugin(), llm_client=_make_mock_llm())
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")
    orch._teaching.set_topic("s1", "u1", ["kp_choice"])
    # 两题都已提交（done=2/2 → exhausted），且都已出过题（quiz_history 排除）
    orch._training.submit("u1", "c1", "B")
    orch._training.submit("u1", "c2", "B")
    state = orch._teaching.get_or_create("s1", "u1")
    state["quiz_history"] = ["c1", "c2"]
    orch._teaching.save(state)
    payload = json.loads(orch._handle_quiz_user(knowledge_point_ids=["kp_choice"]))
    assert payload.get("type") == "essay_ready"
    assert payload.get("progress", {}).get("exhausted") is True
    assert payload.get("progress", {}).get("total") == 2
    assert "简答题" in payload.get("message", "")


def test_generate_essay_handler_returns_essay_json():
    """generate_essay_question → type=essay + question + rubric + teaching.last_quiz。"""
    orch = _orchestrator(MagicMock())
    orch._teaching.set_topic("s1", "u1", ["kp_emergency"])
    fake = MagicMock()
    fake.generate.return_value = MagicMock(
        question_id="essay_abc12345",
        knowledge_point_id="kp_emergency",
        prompt="请说明带团途中遇到游客突发疾病应如何处理。",
        rubric="1.安抚并呼叫急救；2.协同领队与旅行社；3.保留记录与证据。",
    )
    orch._essay_agent = fake
    payload = json.loads(orch._handle_generate_essay_question(knowledge_point_ids=["kp_emergency"]))
    assert payload.get("type") == "essay"
    assert payload["question_id"] == "essay_abc12345"
    assert "question" in payload and "rubric" in payload
    assert payload["teaching"]["last_quiz"]["type"] == "essay"
    fake.generate.assert_called_once()
    args = fake.generate.call_args[0]
    assert args[1]  # topic_titles 非空


def test_submit_essay_handler_grades_and_writes(tmp_path):
    """submit_answer(essay) → 后台智能体判分落库 + 教学状态进入 feedback。"""
    store = SQLiteStore(tmp_path / "essay_sub.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")
    orch._teaching.set_topic("s1", "u1", ["kp_emergency"])
    orch._teaching.record_quiz(
        "s1", "u1", "essay_abc12345",
        question_info={
            "question_id": "essay_abc12345",
            "type": "essay",
            "prompt": "请说明带团途中遇到游客突发疾病应如何处理。",
            "rubric": "1.安抚并呼叫急救；2.协同领队与旅行社；3.保留记录。",
            "difficulty": "advanced",
            "knowledge_point_title": "应急处置",
            "knowledge_point_id": "kp_emergency",
        },
        difficulty="advanced",
    )
    fake = MagicMock()
    fake.grade.return_value = (True, 0.9, "回答得很完整，要点都覆盖了。")
    orch._essay_agent = fake
    payload = json.loads(orch._handle_submit_answer(
        "essay_abc12345", "先安抚游客并呼叫急救，同时联系领队和旅行社，做好记录。", "essay"
    ))
    assert payload.get("correct") is True
    assert payload.get("question_type") == "essay"
    assert payload.get("score") == 0.9
    assert payload["teaching"]["stage"] == "feedback"
    # 落库 + 掌握度联动
    subs = store.get_submissions("u1")
    assert any(s.question_id == "essay_abc12345" for s in subs)
    fake.grade.assert_called_once()


def test_submit_essay_handler_unknown_question_returns_error():
    """提交的 question_id 与当前简答题不匹配 → 明确报错。"""
    orch = _orchestrator(MagicMock())
    orch._teaching.set_topic("s1", "u1", ["kp_emergency"])
    payload = json.loads(orch._handle_submit_answer("essay_unknown", "随便答一下。", "essay"))
    assert "error" in payload


def test_submit_essay_service_writes_submission_and_progress(tmp_path):
    """TrainingService.submit_essay：LLM 判分结果落库 + 掌握度记录联动。"""
    store = SQLiteStore(tmp_path / "essay_svc.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    result = orch._training.submit_essay(
        user_id="u1",
        question_id="essay_abc12345",
        knowledge_point_id="kp_emergency",
        difficulty="advanced",
        prompt="请说明带团途中遇到游客突发疾病应如何处理。",
        rubric="1.安抚呼叫急救；2.协同领队旅行社；3.保留记录。",
        answer="先安抚并呼叫急救，联系领队和旅行社，做好记录。",
        grader=lambda p, r, a: (True, 0.9, "回答完整。"),
    )
    assert result.correct is True
    assert result.score == 0.9
    subs = store.get_submissions("u1")
    assert len(subs) == 1 and subs[0].question_id == "essay_abc12345"
    records = store.get_progress_records("u1", orch._plugin.manifest["plugin_id"])
    assert any(r.knowledge_point_id == "kp_emergency" and r.mastery == 1.0 for r in records)


def test_submit_essay_service_wrong_answer_scores_low(tmp_path):
    """答得差 → 判分低分 + correct=False。"""
    store = SQLiteStore(tmp_path / "essay_low.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    result = orch._training.submit_essay(
        user_id="u1",
        question_id="essay_xyz",
        knowledge_point_id="kp_emergency",
        difficulty="advanced",
        prompt="如何处理游客突发疾病？",
        rubric="1.安抚呼叫急救；2.协同领队；3.保留记录。",
        answer="不知道。",
        grader=lambda p, r, a: (False, 0.1, "回答过于简略，未覆盖任何要点。"),
    )
    assert result.correct is False
    assert result.score == 0.1
    assert "要点" in result.feedback


# ═══════════════ 完整流程：管家工具链打通 ═══════════════

def test_full_flow_quiz_then_essay_then_submit(tmp_path):
    """完整闭环：quiz_user（选择题）→ 全做完 → generate_essay_question（简答）→ submit_answer(essay)。"""
    from brain_of_cloud.domain.models import Question
    from brain_of_cloud.plugins import InboundGuidePlugin

    class _ChoicePlugin(InboundGuidePlugin):
        def __init__(self) -> None:
            super().__init__()
            self._questions = [
                Question(
                    question_id="c1", knowledge_point_id="kp_choice", difficulty="intro",
                    prompt="一五计划的起止时间是？",
                    options=["A. 1950～1954", "B. 1953～1957", "C. 1956～1960", "D. 1958～1962"],
                    answer="B", explanation="1953～1957 年。",
                ),
            ]

    store = SQLiteStore(tmp_path / "essay_flow.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=_ChoicePlugin(), llm_client=_make_mock_llm())
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")
    orch._teaching.set_topic("s1", "u1", ["kp_choice"])
    fake = MagicMock()
    fake.generate.return_value = MagicMock(
        question_id="essay_flow01", knowledge_point_id="kp_choice",
        prompt="请谈谈一五计划的历史意义。", rubric="要点：工业化基础、计划体制、民生改善。",
    )
    fake.grade.return_value = (True, 0.85, "答得不错，补充一点：一五计划奠定了工业化基础。")
    orch._essay_agent = fake

    # 第 1 轮：quiz_user 出选择题
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "quiz_user", "arguments": {"knowledge_point_ids": ["kp_choice"]}}]
    )
    r1 = orch.handle_user_message("u1", "s1", "讲完了，出题吧")
    assert r1.task.status == TaskStatus.COMPLETED
    assert "quiz_user" in r1.tool_calls_made
    assert r1.teaching and r1.teaching["last_quiz"]["type"] == "choice"

    # 答对（选择 B）
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "submit_answer",
                  "arguments": {"question_id": "c1", "answer": "B"}}]
    )
    r2 = orch.handle_user_message("u1", "s1", "我选 B")
    assert "submit_answer" in r2.tool_calls_made

    # 第 2 轮：选择题已做完 → 管家转简答题
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "generate_essay_question",
                  "arguments": {"knowledge_point_ids": ["kp_choice"]}}]
    )
    r3 = orch.handle_user_message("u1", "s1", "来道简答题吧")
    assert "generate_essay_question" in r3.tool_calls_made
    assert r3.teaching and r3.teaching["last_quiz"]["type"] == "essay"
    assert r3.teaching["last_quiz"]["rubric"]

    # 简答提交
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "submit_answer",
                  "arguments": {"question_id": "essay_flow01",
                                "answer": "一五计划奠定了工业化基础。",
                                "question_type": "essay"}}]
    )
    r4 = orch.handle_user_message("u1", "s1", "我的回答：一五计划奠定了工业化基础。")
    assert "submit_answer" in r4.tool_calls_made
    subs = store.get_submissions("u1")
    assert any(s.question_id == "essay_flow01" for s in subs)
    assert fake.grade.called
