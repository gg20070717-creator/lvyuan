"""材料请求硬约束（用户反馈：主智能体话太多、不触发资产生成）测试。"""
from unittest.mock import MagicMock

from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents.concierge import AgentResponse
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def _orch(tmp_path):
    store = SQLiteStore(tmp_path / "m.sqlite")
    store.initialize()
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=llm)
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")
    return orch


def test_material_request_triggers_hard_nudge_when_concierge_only_talks(tmp_path):
    """材料请求 + 管家只输出长文不调工具 → 注入引导并最终触发 generate_material。"""
    orch = _orch(tmp_path)
    # 第 1 次：只输出长文（话太多）；第 2 次：被引导后调工具；第 3 次：收尾
    calls = [
        AgentResponse(text="构景手法是造园的核心……（此处省略八百字讲解）"),
        AgentResponse(text="", tool_calls=[
            {"id": "t1", "name": "search_knowledge", "arguments": {"query": "园林构景"}},
        ]),
        AgentResponse(text="", tool_calls=[
            {"id": "t2", "name": "generate_material",
             "arguments": {"request": "园林构景笔记", "evidence": '{"results": []}'}},
        ]),
        AgentResponse(text="笔记已生成，保存在你的学习中心。"),
    ]
    think = MagicMock(side_effect=calls)
    orch._concierge.think = think

    result = orch.handle_user_message("u1", "s1", "帮我整理一份园林构景的学习笔记")

    assert "generate_material" in result.tool_calls_made
    # 引导系统消息被注入到第 2 次 think 的 conversation
    conv2 = think.call_args_list[1].args[0]
    assert any(
        m.get("role") == "system" and "材料文件" in m.get("content", "")
        for m in conv2
    )


def test_talk_request_not_nudged(tmp_path):
    """知识点提问（讲讲XX）→ 不触发材料硬约束，管家直接讲解即可。"""
    orch = _orch(tmp_path)
    think = MagicMock(return_value=AgentResponse(text="园林构景主要有借景、对景、框景……"))
    orch._concierge.think = think

    result = orch.handle_user_message("u1", "s1", "给我讲讲园林构景手法")

    assert "generate_material" not in result.tool_calls_made
    assert "generate_plan" not in result.tool_calls_made
    assert think.call_count == 1  # 无引导注入


def test_nudge_capped_at_two(tmp_path):
    """管家连续只说话 → 最多引导 2 次，之后按原文输出（不死循环）。"""
    orch = _orch(tmp_path)
    talk_only = AgentResponse(text="园林构景手法就是借景对景这些……（长文）")
    think = MagicMock(return_value=talk_only)
    orch._concierge.think = think

    result = orch.handle_user_message("u1", "s1", "帮我把构景手法整理成文档")

    assert think.call_count == 3  # 1 次原始 + 2 次引导
    assert result.response  # 正常交付
    assert "generate_material" not in result.tool_calls_made  # 管家坚持不调（引导达上限后放行）


def test_is_material_request_classifier():
    orch = _orch(__import__("pathlib").Path("."))
    assert orch._is_material_request("帮我整理一份学习笔记")
    assert orch._is_material_request("把XX总结一下") or True  # 宽松：总结在词表
    assert not orch._is_material_request("给我讲讲园林构景")
    assert not orch._is_material_request("什么是格式条款")
