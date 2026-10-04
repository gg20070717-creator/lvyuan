"""Test the tool-driven orchestrator."""
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


def _make_mock_concierge(text="你好！有什么想了解的地陪导游知识吗？"):
    """Create a mock concierge that returns canned responses."""
    from brain_of_cloud.services.agents.concierge import AgentResponse
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试用管家")
    mc.think.return_value = AgentResponse(text=text)
    return mc


def test_short_chat_returns_concierge_response(tmp_path):
    """Short chat: concierge responds directly without calling any tools."""
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orchestrator._concierge = _make_mock_concierge()

    result = orchestrator.handle_user_message("user_1", "session_1", "你好")

    assert result.task.status == TaskStatus.COMPLETED
    assert "你好" in result.response
    assert result.tool_calls_made == []


def test_tool_call_flow(tmp_path):
    """Concierge calls tools: first generate, then review, then responds."""
    from brain_of_cloud.services.agents.concierge import AgentResponse
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())

    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    call_count = [0]
    def think(conversation, tools=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return AgentResponse(text="好的，我来生成。",
                tool_calls=[{"id": "t1", "name": "generate_material",
                    "arguments": {"request": "欢迎词脚本", "evidence": "{}"}}])
        elif call_count[0] == 2:
            return AgentResponse(text="写完后再审查。",
                tool_calls=[{"id": "t2", "name": "review_material",
                    "arguments": {"content": "欢迎词训练材料..."}}])
        else:
            return AgentResponse(text="材料已生成并通过审查，请查看。")
    mc.think.side_effect = think
    orchestrator._concierge = mc

    result = orchestrator.handle_user_message("user_1", "session_1", "请生成一段欢迎词训练脚本")

    assert result.task.status == TaskStatus.COMPLETED
    assert "generate_material" in result.tool_calls_made
    assert "review_material" in result.tool_calls_made
    # 协同链路：生成 → 审查 顺序（前端据此渲染「内容生成→六帽审查」）
    assert result.tool_calls_made.index("generate_material") < result.tool_calls_made.index("review_material")
    assert len(result.response) > 0


def test_agent_runs_recorded_for_each_tool_call(tmp_path):
    """每次工具调用写入 agent_runs（群组空间审计，差距项 T5）。"""
    from brain_of_cloud.services.agents.concierge import AgentResponse
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())

    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    call_count = [0]
    def think(conversation, tools=None):
        call_count[0] += 1
        if call_count[0] == 1:
            return AgentResponse(text="检索一下。",
                tool_calls=[{"id": "t1", "name": "search_knowledge",
                    "arguments": {"query": "欢迎词"}}])
        else:
            return AgentResponse(text="已回复。")
    mc.think.side_effect = think
    orchestrator._concierge = mc

    result = orchestrator.handle_user_message("user_1", "session_1", "欢迎词怎么写？")

    runs = store.list_agent_runs(result.task.task_id)
    assert len(runs) == 1
    assert runs[0].agent_id.value == "retrieval"
    assert runs[0].status.value == "completed"
    # 用户消息带结构化 mentions（管家→检索）
    messages = store.list_messages(result.task.task_id)
    user_msg = [m for m in messages if m.from_agent.value == "concierge"][0]
    assert any(m.agent_id.value == "retrieval" for m in user_msg.mentions)


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
        return AgentResponse(text="已生成，请查看。")
    mc.think.side_effect = think
    return mc


def test_generate_material_creates_asset(tmp_path):
    """generate_material 产物落库为学习中心文件资产。"""
    store = SQLiteStore(tmp_path / "assets.sqlite")
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orchestrator._text_generator.run = MagicMock(return_value="一、接站准备流程\n1. 核对名单…")
    orchestrator._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "generate_material",
                  "arguments": {"request": "请生成接站实操指南", "evidence": "{}"}}]
    )

    result = orchestrator.handle_user_message("user_1", "session_1", "给我一份接站实操指南")

    assert result.assets, "应创建文件资产"
    assert result.assets[0]["asset_type"] == "practice_guide"  # 含「实操/指南」→ 实操指南
    rows = store.get_assets("user_1")
    assert len(rows) == 1
    assert rows[0]["source_tool"] == "generate_material"
    assert "接站准备流程" in rows[0]["content"]
    assert "学习中心" in result.response  # 交付语告知已保存


def test_generate_material_appends_source_references(tmp_path):
    """资产内容末尾追加「参考来源」章节（引用链，差距项 T8）。"""
    store = SQLiteStore(tmp_path / "refs.sqlite")
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orchestrator._text_generator.run = MagicMock(return_value="欢迎词正文…")
    orchestrator._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "generate_material",
                  "arguments": {
                      "request": "欢迎词脚本",
                      "evidence": json.dumps({
                          "results": [
                              {"chunk_id": "ev_welcome", "content": "欢迎词要素…",
                               "source": "导游业务教材", "trust": 0.92},
                          ]
                      }),
                  }}]
    )

    orchestrator.handle_user_message("user_1", "session_1", "写个欢迎词脚本")

    rows = store.get_assets("user_1")
    assert len(rows) == 1
    content = rows[0]["content"]
    assert "参考来源" in content
    assert "导游业务教材" in content


def test_generate_plan_creates_asset(tmp_path):
    """generate_plan 产物落库为「学习计划」资产。"""
    store = SQLiteStore(tmp_path / "plan.sqlite")
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orchestrator._planner.run = MagicMock(return_value="第1周：学习《政策与法律法规》…")
    orchestrator._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "generate_plan", "arguments": {}}]
    )

    result = orchestrator.handle_user_message("user_1", "session_1", "帮我制定备考计划")

    assert result.assets
    assert result.assets[0]["asset_type"] == "plan"
    rows = store.get_assets("user_1")
    assert rows and rows[0]["asset_type"] == "plan"
    assert rows[0]["source_tool"] == "generate_plan"


def test_generate_report_creates_asset(tmp_path):
    """generate_report 产物落库为「学习报告」资产。"""
    from brain_of_cloud.domain.models import MasteryReport
    store = SQLiteStore(tmp_path / "report.sqlite")
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())
    orchestrator._analyzer.run = MagicMock(
        return_value=MasteryReport(
            report_id="r1", user_id="user_1",
            knowledge_point_scores={}, weak_points=[],
            recommended_action="建议先复习接站流程。",
        )
    )
    orchestrator._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "generate_report", "arguments": {}}]
    )

    result = orchestrator.handle_user_message("user_1", "session_1", "给我学习报告")

    assert result.assets
    assert result.assets[0]["asset_type"] == "report"
    rows = store.get_assets("user_1")
    assert rows and rows[0]["asset_type"] == "report"
    assert "建议先复习接站流程" in rows[0]["content"]


def test_repeat_correct_flag(tmp_path):
    """重复答对已掌握的题 → submit_answer 返回 repeat_correct=True（编排器据此直接换新题，防死循环）。"""
    import json as _json
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
    orchestrator = Orchestrator(store=store, plugin=TourGuidePlugin(), llm_client=_make_mock_llm())
    orchestrator._concierge = _make_mock_concierge()
    # 设置上下文（handle_user_message 内部 set _current_user_id/_current_session_id）
    orchestrator.handle_user_message("user_repeat", "session_repeat", "你好")

    # 取一道带选项的题（选择题池排除简答）
    q = orchestrator._training.random_quiz(n=1, knowledge_point_ids=None, difficulty=None)[0]
    assert q.options, "测试需要带选项的题"
    ans = q.answer or "A"

    r1 = _json.loads(orchestrator._handle_submit_answer(q.question_id, ans))
    r2 = _json.loads(orchestrator._handle_submit_answer(q.question_id, ans))
    assert r1.get("repeat_correct") is False, r1
    assert r2.get("repeat_correct") is True, r2


def test_repeat_correct_injects_new_quiz(tmp_path):
    """重复答对已掌握的题 → 编排器直接抽新题注入对话，不再死循环/不再停留旧题。"""
    from brain_of_cloud.services.agents.concierge import AgentResponse
    from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
    import json as _json
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=TourGuidePlugin(), llm_client=_make_mock_llm())
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    st = {"turn": 0, "qid": None, "ans": None, "new_qid": None}

    def _quiz_result(conversation):
        for m in reversed(conversation):
            if m.get("role") == "tool" and isinstance(m.get("content"), str) and '"question_id"' in m["content"]:
                return _json.loads(m["content"])
        return None

    def think(conversation, tools=None):
        st["turn"] += 1
        if st["turn"] == 1:
            return AgentResponse(text="第一题", tool_calls=[{"id": "t1", "name": "quiz_user", "arguments": {}}])
        if st["turn"] == 2:
            r = _quiz_result(conversation)
            st["qid"] = r["question_id"]
            bank = _json.loads(open("data/master_question_bank.json", encoding="utf-8").read())
            q = next((x for x in bank["questions"] if x["题目"] == r["question"]), None)
            st["ans"] = q["答案"] if q else "A"
            return AgentResponse(text="判分", tool_calls=[{
                "id": "t2", "name": "submit_answer",
                "arguments": {"question_id": st["qid"], "answer": st["ans"]},
            }])
        if st["turn"] == 3:
            return AgentResponse(text="判分", tool_calls=[{
                "id": "t3", "name": "submit_answer",
                "arguments": {"question_id": st["qid"], "answer": st["ans"]},
            }])
        # 第 4 轮：重复答对后编排器已注入新题，管家收尾
        return AgentResponse(text="好的，这是下一道新题，继续作答。")

    mc.think.side_effect = think
    orch._concierge = mc
    # 预置教学主题（真实场景由「去首页学习」硬挂钩锁定），否则 quiz_user 拒绝出题
    orch._teaching.set_topic("session_rep2", "user_rep2", ["cc__us__culture__food_000"])
    result = orch.handle_user_message("user_rep2", "session_rep2", "考考我")

    assert result.tool_calls_made.count("submit_answer") == 2  # 两次判分都执行完，未死循环
    assert result.tool_calls_made.count("quiz_user") >= 1
    # 重复答对后，教学状态里的 last_quiz 应已换成新题（或题已出完给提示），而不是停在旧题
    teaching = (result.teaching or {}).get("last_quiz") or {}
    if teaching.get("question_id"):
        assert teaching["question_id"] != st["qid"], "重复答对后仍停在旧题（应换新题）"
