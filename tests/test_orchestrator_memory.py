"""Orchestrator-level tests: session persistence, memory, planner, review loop."""

from unittest.mock import MagicMock

from brain_of_cloud.domain.models import TaskStatus
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.services.agents.concierge import AgentResponse
from brain_of_cloud.storage.sqlite import SQLiteStore


def _make_llm():
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    return llm


def _make_orch(store, plugin=None):
    plugin = plugin or TourGuidePlugin()
    orch = Orchestrator(store=store, plugin=plugin, llm_client=_make_llm())
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试管家")
    mc.think.return_value = AgentResponse(text="好的。")
    orch._concierge = mc
    return orch


def _canned_concierge(sequence):
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试管家")
    mc.think.side_effect = sequence
    return mc


def test_session_persisted_and_reloaded(tmp_path):
    store = SQLiteStore(tmp_path / "a.sqlite")
    store.initialize()
    orch = _make_orch(store)
    orch._concierge = _canned_concierge([
        AgentResponse(text="你好！我是管家。"),
        AgentResponse(text="好的，我来介绍。"),
    ])

    orch.handle_user_message("u1", "s1", "我想备考导游证")
    orch.handle_user_message("u1", "s1", "帮我介绍一下政策与法律法规")

    saved = store.get_session_messages("s1")
    assert any(m["role"] == "user" and "备考导游证" in m["content"] for m in saved)
    assert any(m["role"] == "assistant" and "你好" in m["content"] for m in saved)
    assert sum(1 for m in saved if m["role"] == "user") == 2

    # 模拟重启：新实例从 SQLite 恢复历史
    orch2 = Orchestrator(store=store, plugin=TourGuidePlugin(), llm_client=_make_llm())
    # 恢复后会话应包含历史 user/assistant 消息
    hist = orch2._store.get_session_messages("s1")
    assert len(hist) >= 4


def test_memory_extracted_during_chat(tmp_path):
    store = SQLiteStore(tmp_path / "b.sqlite")
    store.initialize()
    orch = _make_orch(store)
    orch.handle_user_message("u2", "s2", "我叫王小明，目标是考到导游证")

    mems = store.get_memories("u2")
    contents = [str(m["content"]) for m in mems]
    assert any("王小明" in c for c in contents)
    assert any("导游证" in c for c in contents)


def test_profile_injected_into_context(tmp_path):
    from brain_of_cloud.domain.models import LearnerProfile

    store = SQLiteStore(tmp_path / "c.sqlite")
    store.initialize()
    store.save_learner_profile(
        LearnerProfile(
            user_id="u3", background="旅游管理专业大二",
            target_role="导游资格证", current_level="basic",
            style_preferences={"mode": "实操优先"},
        )
    )
    orch = _make_orch(store)
    seen_conversations = []

    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试管家")

    def think(conversation, tools=None):
        seen_conversations.append(list(conversation))
        return AgentResponse(text="好的。")

    mc.think.side_effect = think
    orch._concierge = mc
    orch.handle_user_message("u3", "s3", "你好")

    # 上下文中应注入学员档案（画像 + 目标 + 风格）
    ctx = "".join(
        str(m.get("content", "")) for m in seen_conversations[0] if m["role"] == "system"
    )
    assert "旅游管理专业大二" in ctx
    assert "导游资格证" in ctx
    assert "实操优先" in ctx


def test_planner_tool_returns_plan(tmp_path):
    store = SQLiteStore(tmp_path / "d.sqlite")
    store.initialize()
    orch = _make_orch(store)
    orch._planner = MagicMock()
    orch._planner.run.return_value = "阶段一：夯实基础……"
    orch._user_id_ctx.set("u4")

    content = orch._handle_generate_plan()
    import json
    data = json.loads(content)
    assert "阶段一" in data["plan"]
    assert isinstance(data["weak_point_titles"], list)


def test_review_needs_revision_triggers_redirection(tmp_path):
    """审查不通过时，下一轮对话应包含修订指令。"""
    store = SQLiteStore(tmp_path / "e.sqlite")
    store.initialize()
    orch = _make_orch(store)

    call_count = [0]
    seen_convs = []

    def think(conversation, tools=None):
        seen_convs.append([dict(m) for m in conversation])
        call_count[0] += 1
        if call_count[0] == 1:
            return AgentResponse(
                text="生成材料。",
                tool_calls=[{"id": "t1", "name": "generate_material",
                             "arguments": {"request": "讲义", "evidence": "{}"}}],
            )
        if call_count[0] == 2:
            return AgentResponse(
                text="审查。",
                tool_calls=[{"id": "t2", "name": "review_material",
                             "arguments": {"content": "讲义内容"}}],
            )
        return AgentResponse(text="已修订并再次审查。")

    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试管家")
    mc.think.side_effect = think
    orch._concierge = mc

    # mock 六帽返回"需修改"
    from brain_of_cloud.services.agents.base import AgentResult
    mock_hats = {}
    for aid in ["white_hat", "black_hat", "green_hat", "yellow_hat", "red_hat"]:
        h = MagicMock()
        h.run.return_value = AgentResult(content="测试审查", passed=False)
        mock_hats[aid] = h
    orch._white_hat = mock_hats["white_hat"]
    orch._black_hat = mock_hats["black_hat"]
    orch._green_hat = mock_hats["green_hat"]
    orch._yellow_hat = mock_hats["yellow_hat"]
    orch._red_hat = mock_hats["red_hat"]
    orch._blue_hat = MagicMock()
    orch._blue_hat.coordinate.return_value = "蓝帽检测：需修改。存在事实性问题。"

    result = orch.handle_user_message("u5", "s5", "给我生成一份政策法规讲义")

    # 第三轮对话应包含"修订"指令系统消息
    assert len(seen_convs) >= 3
    third_system_text = "".join(
        str(m.get("content", ""))
        for m in seen_convs[2]
        if m.get("role") == "system"
    )
    assert "审查意见" in third_system_text or "修订" in third_system_text
    assert result.task.status == TaskStatus.COMPLETED
