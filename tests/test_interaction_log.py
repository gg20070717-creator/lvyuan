"""消息交互日志（T15 / D-8）：智能体交互留痕，供画像偏好提取与审计。"""
from unittest.mock import MagicMock

from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def test_append_and_list_logs(tmp_path):
    store = SQLiteStore(tmp_path / "l.sqlite")
    store.initialize()

    store.append_interaction_log(
        user_id="u1", task_id="t1", message_id="m1",
        from_agent="concierge", to_agents=["retrieval"],
        action="tool:search_knowledge", content_summary="检索了园林构景",
    )
    store.append_interaction_log(
        user_id="u1", task_id="t1", message_id="m1",
        from_agent="text_generator", to_agents=["concierge"],
        action="tool:generate_material", content_summary="生成了讲义",
    )

    logs = store.list_interaction_logs("u1")
    assert len(logs) == 2
    first = logs[0]  # 最新在前
    assert first["from_agent"] == "text_generator"
    assert first["action"] == "tool:generate_material"
    assert first["to_agents"] == ["concierge"]
    assert "讲义" in first["content_summary"]
    # 摘要截断 300 字符
    store.append_interaction_log(
        user_id="u1", task_id="t1", message_id="m1",
        from_agent="concierge", action="tool:quiz_user",
        content_summary="长" * 500,
    )
    assert len(store.list_interaction_logs("u1")[0]["content_summary"]) <= 300


def test_logs_deleted_with_user_data(tmp_path):
    store = SQLiteStore(tmp_path / "l2.sqlite")
    store.initialize()
    store.append_interaction_log(
        user_id="u1", task_id="t1", message_id="m1",
        from_agent="concierge", action="tool:search_knowledge",
    )

    store.delete_user_data("u1", InboundGuidePlugin().manifest["plugin_id"])

    assert store.list_interaction_logs("u1") == []


def test_orchestrator_writes_logs_on_tool_call(tmp_path):
    """管家调用工具 → orchestrator 写入交互日志（真实链路）。"""
    store = SQLiteStore(tmp_path / "l3.sqlite")
    store.initialize()
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=llm)
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")

    # 管家返回一次工具调用（search_knowledge），工具执行后管家收尾
    from brain_of_cloud.services.agents.concierge import AgentResponse
    think = MagicMock(side_effect=[
        AgentResponse(text="", tool_calls=[{"id": "t1", "name": "search_knowledge", "arguments": {"query": "园林构景"}}]),
        AgentResponse(text="查到了，园林构景主要有借景、对景、框景……"),
    ])
    orch._concierge.think = think

    result = orch.handle_user_message("u1", "s1", "给我讲讲园林构景")

    assert result.response
    logs = store.list_interaction_logs("u1")
    assert len(logs) >= 1
    assert logs[0]["action"] == "tool:search_knowledge"
    assert logs[0]["from_agent"] == "retrieval"
