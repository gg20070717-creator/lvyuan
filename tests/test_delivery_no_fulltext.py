"""生成资产后管家交付不得复述文件全文（材料正文只进资产文件，不进聊天回复）。

回归目标：修「生成文件时管家直接把文件内容作为回复」问题。
- 工具结果注入对话时裁剪（模型看不到全文 → 无法复述）
- 交付兜底路径（管家交付失败 / 迭代耗尽）不再输出全文
"""
import json
from unittest.mock import MagicMock

from brain_of_cloud.domain.models import TaskStatus
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents.concierge import AgentResponse
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore

FULL_CONTENT = (
    "一、接站准备流程\n"
    "1. 核对名单（务必逐人确认证件与行李）\n"
    "2. 欢迎词要点：欢迎来到上海，行程共三天……\n"
    "3. 协助上车与行李摆放，提醒系好安全带\n"
    "二、途中服务\n"
    "1. 介绍上海概况与外滩历史\n"
    "2. 提醒注意事项：随身物品、集合时间\n"
) * 3


def _make_orchestrator(tmp_path):
    store = SQLiteStore(tmp_path / "delivery.sqlite")
    store.initialize()
    return Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=MagicMock(model="m"))


def _canned_think_with_capture(captured: dict):
    """第 1 次调用 generate_material；第 2 次捕获对话并返回指定文本。"""
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    state = {"n": 0}

    def think(conversation, tools=None):
        state["n"] += 1
        if state["n"] == 1:
            return AgentResponse(
                text="好的，我来生成。",
                tool_calls=[{"id": "t1", "name": "generate_material",
                             "arguments": {"request": "接站指南", "evidence": "{}"}}],
            )
        captured["conversation"] = [dict(m) for m in conversation]
        return AgentResponse(text="材料已生成，保存在你的学习中心。")
    mc.think.side_effect = think
    return mc


def test_tool_result_injected_without_full_content(tmp_path):
    """generate_material 的工具结果注入对话时不得包含材料全文（防管家复述）。"""
    orch = _make_orchestrator(tmp_path)
    orch._text_generator.run = MagicMock(return_value=FULL_CONTENT)
    captured: dict = {}
    orch._concierge = _canned_think_with_capture(captured)

    result = orch.handle_user_message("user_1", "s1", "给我一份接站指南")

    assert result.task.status == TaskStatus.COMPLETED
    tool_msgs = [m for m in captured["conversation"] if m.get("role") == "tool"]
    assert tool_msgs, "应有工具结果消息"
    joined = "\n".join(str(m.get("content", "")) for m in tool_msgs)
    assert "核对名单" not in joined, "工具结果不应注入材料全文（模型会复述）"
    # 资产本身完整入库
    rows = orch._store.get_assets("user_1")
    assert rows and "核对名单" in rows[0]["content"]


def test_delivery_fallback_never_dumps_full_content(tmp_path):
    """审查通过后管家交付轮无输出 → 兜底交付语不得直接输出文件全文。"""
    orch = _make_orchestrator(tmp_path)
    orch._text_generator.run = MagicMock(return_value=FULL_CONTENT)

    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    state = {"n": 0}

    def think(conversation, tools=None):
        state["n"] += 1
        if state["n"] == 1:
            return AgentResponse(
                text="好的。",
                tool_calls=[{"id": "t1", "name": "generate_material",
                             "arguments": {"request": "接站指南", "evidence": "{}"}}],
            )
        return AgentResponse(text="", tool_calls=[])  # 交付轮无输出 → 触发兜底
    mc.think.side_effect = think
    orch._concierge = mc

    result = orch.handle_user_message("user_1", "s1", "给我一份接站指南")

    assert result.task.status == TaskStatus.COMPLETED
    assert "核对名单" not in result.response, "兜底交付不得输出全文"
    assert "学习中心" in result.response


def test_exhausted_loop_fallback_no_full_content(tmp_path):
    """迭代耗尽且无最终交付文本 → 兜底回复不得输出全文。"""
    orch = _make_orchestrator(tmp_path)
    orch._text_generator.run = MagicMock(return_value=FULL_CONTENT)

    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    state = {"n": 0}

    def think(conversation, tools=None):
        state["n"] += 1
        if state["n"] == 1:
            return AgentResponse(
                text="好的。",
                tool_calls=[{"id": "t1", "name": "generate_material",
                             "arguments": {"request": "接站指南", "evidence": "{}"}}],
            )
        return AgentResponse(text="", tool_calls=[])  # 之后一直空输出 → 迭代耗尽
    mc.think.side_effect = think
    orch._concierge = mc

    result = orch.handle_user_message("user_1", "s1", "给我一份接站指南")

    assert result.task.status == TaskStatus.COMPLETED
    assert "核对名单" not in result.response, "迭代耗尽兜底不得输出全文"
    assert result.response  # 有兜底文案
