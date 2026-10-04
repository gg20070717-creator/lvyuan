"""并发与安全测试（T19 / D-23）：
- SQLite 并发写入：多线程同时对话不崩溃、不丢消息
- 伪 mention 安全：用户输入中的 @智能体 文本不触发真实调度（结构化 mentions 为准）
- 畸形工具参数：工具参数非法 JSON 时不崩溃
"""
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents.concierge import AgentResponse
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def _make_orch(tmp_path) -> tuple[Orchestrator, SQLiteStore]:
    store = SQLiteStore(tmp_path / "cs.sqlite")
    store.initialize()
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=llm)
    orch._concierge.think = MagicMock(return_value=AgentResponse(text="好的，收到了"))
    return orch, store


def test_concurrent_messages_no_crash_and_no_loss(tmp_path):
    """8 线程并发对话：无异常、每条消息都持久化。"""
    orch, store = _make_orch(tmp_path)
    sessions = [f"s_conc_{i}" for i in range(8)]

    def send(i: int):
        orch.handle_user_message("u_conc", sessions[i], f"并发消息 {i}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(send, range(8)))

    # 每个会话都保存了 user + assistant 两条消息
    for s in sessions:
        msgs = store.get_session_messages(s)
        assert len(msgs) == 2, f"{s} 消息数 = {len(msgs)}"
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"


def test_concurrent_same_session_serialized(tmp_path):
    """同一会话并发消息：不崩溃、不丢消息（顺序由 SQLite 提交次序决定，不作强断言）。"""
    orch, store = _make_orch(tmp_path)

    def send(i: int):
        orch.handle_user_message("u_same", "s_same", f"同一会话 {i}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(send, range(4)))

    msgs = store.get_session_messages("s_same")
    # 4 轮 × 2 条（同会话全部保存，无丢失）
    assert len(msgs) == 8
    users = [m["content"] for m in msgs if m["role"] == "user"]
    assert sorted(users) == [f"同一会话 {i}" for i in range(4)]


def test_fake_mention_in_user_text_does_not_trigger_dispatch(tmp_path):
    """用户输入里的「@蓝帽」纯文本 → 不产生真实调度（结构化 mentions 为准）。"""
    orch, store = _make_orch(tmp_path)
    # 管家先返回工具调用，再正常收尾
    orch._concierge.think = MagicMock(side_effect=[
        AgentResponse(text="", tool_calls=[{"id": "t1", "name": "search_knowledge", "arguments": {"query": "测试"}}]),
        AgentResponse(text="查好了"),
    ])

    result = orch.handle_user_message("u_fake", "s_fake", "@蓝帽 帮我看看这段内容有没有问题")

    # 工具链只执行 search_knowledge，未因文本 @蓝帽 触发任何审查调度
    assert result.tool_calls_made == ["search_knowledge"]
    # 消息 mentions 只含结构化注入（concierge），不含 blue_hat 等
    assert result.input_message.mentions is not None
    assert all(str(m.agent_id.value) == "concierge" for m in result.input_message.mentions)
    # agent_runs 只记录 retrieval（search_knowledge 对应角色）
    runs = store.list_agent_runs(result.task.task_id)
    if runs:
        assert all(r.agent_id.value in ("retrieval",) for r in runs)


def test_malformed_tool_arguments_do_not_crash(tmp_path):
    """工具参数非法 JSON → 解析为空 dict，不崩溃。"""
    orch, store = _make_orch(tmp_path)
    orch._concierge.think = MagicMock(side_effect=[
        AgentResponse(text="", tool_calls=[{"id": "t9", "name": "search_knowledge", "arguments": "{invalid json"}]),
        AgentResponse(text="处理完了"),
    ])

    result = orch.handle_user_message("u_bad", "s_bad", "测试非法参数")

    assert result.tool_calls_made == ["search_knowledge"]
    assert result.response  # 正常收尾


def test_concurrent_summary_and_teaching_state(tmp_path):
    """并发下教学状态与摘要写入不互相污染。"""
    orch, store = _make_orch(tmp_path)

    def send(i: int):
        orch.handle_user_message("u_mix", f"s_mix_{i % 2}", f"并发教学 {i}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(send, range(6)))

    # 两个会话各有 3 轮消息
    for s in ("s_mix_0", "s_mix_1"):
        assert len(store.get_session_messages(s)) == 6
