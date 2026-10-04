"""讲解/答疑自动存档测试：管家每次知识点讲解都生成文档留存（学习中心资产）。"""
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


def _orchestrator(tmp_path):
    store = SQLiteStore(tmp_path / "archive.sqlite")
    store.initialize()
    return Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=_make_mock_llm())


def _canned_concierge(plan, final_text="一五计划是新中国第一个五年计划，1953到1957年，"
                                       "在苏联帮助下优先发展重工业，初步建立了独立工业体系。"
                                       "这是中国工业化建设的起点，具有里程碑意义。"):
    """Concierge mock：第 1 次调用触发工具，之后返回讲解文本。"""
    from brain_of_cloud.services.agents.concierge import AgentResponse
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    state = {"n": 0}
    def think(conversation, tools=None):
        state["n"] += 1
        if state["n"] == 1:
            return AgentResponse(text="好的，我来查一下。", tool_calls=plan())
        return AgentResponse(text=final_text)
    mc.think.side_effect = think
    return mc


def _lecture_assets(orch, user_id):
    return [a for a in orch._store.get_assets(user_id)
            if a["source_tool"] == "lecture_archive"]


def test_lecture_archive_after_knowledge_teaching(tmp_path):
    """管家检索知识库并讲解 → 自动生成「讲解笔记」资产留存。"""
    orch = _orchestrator(tmp_path)
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "search_knowledge", "arguments": {"query": "一五计划"}}]
    )
    result = orch.handle_user_message("u1", "s1", "给我讲讲一五计划")
    assert result.task.status == TaskStatus.COMPLETED
    assets = _lecture_assets(orch, "u1")
    assert len(assets) == 1, "应生成 1 份讲解笔记"
    assert "讲解笔记" in assets[0]["title"]
    assert assets[0]["asset_type"] == "lecture"
    # 内容含问题与讲解全文
    assert "给我讲讲一五计划" in assets[0]["content"]
    assert "一五计划是新中国第一个五年计划" in assets[0]["content"]
    # 回复附轻提示
    assert "存档" in result.response


def test_lecture_archive_sources_extracted(tmp_path):
    """存档内容包含知识来源（search_knowledge 结果出处）。"""
    orch = _orchestrator(tmp_path)
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "search_knowledge", "arguments": {"query": "emergency"}}]
    )
    orch.handle_user_message("u1", "s1", "外国游客护照丢了怎么处理？")
    assets = _lecture_assets(orch, "u1")
    assert assets, "应有讲解笔记"
    assert "知识来源" in assets[0]["content"]
    assert "built-in" in assets[0]["content"] or "inbound" in assets[0]["content"]


def test_lecture_archive_skipped_for_material_request(tmp_path):
    """材料生产请求（生成讲义）→ 不额外生成讲解笔记（避免重复存档）。"""
    orch = _orchestrator(tmp_path)
    orch._text_generator.run = MagicMock(return_value="一、接站准备流程\n1. 核对名单…")
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "search_knowledge", "arguments": {"query": "接站"}},
                 {"id": "t2", "name": "generate_material",
                  "arguments": {"request": "接站实操指南", "evidence": "{}"}}],
        final_text="接站指南已生成，保存在你的学习中心。",
    )
    result = orch.handle_user_message("u1", "s1", "给我生成一份接站实操指南")
    assert result.assets, "材料路径应生成资产"
    assert not _lecture_assets(orch, "u1"), "材料路径不应额外生成讲解笔记"


def test_lecture_archive_skipped_for_chitchat(tmp_path):
    """纯闲聊（无检索）→ 不生成讲解笔记。"""
    orch = _orchestrator(tmp_path)
    from brain_of_cloud.services.agents.concierge import AgentResponse
    mc = MagicMock()
    mc.config = MagicMock(system_prompt="测试")
    mc.think.return_value = AgentResponse(text="你好呀！今天想学点什么？")
    orch._concierge = mc
    orch.handle_user_message("u1", "s1", "你好")
    assert not _lecture_assets(orch, "u1")


def test_lecture_archive_skipped_for_short_reply(tmp_path):
    """回复过短（工具交付语，非实质讲解）→ 不生成。"""
    orch = _orchestrator(tmp_path)
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "search_knowledge", "arguments": {"query": "一五计划"}}],
        final_text="查到了。",
    )
    orch.handle_user_message("u1", "s1", "讲讲一五计划")
    assert not _lecture_assets(orch, "u1")


def test_lecture_archive_every_teaching_round(tmp_path):
    """同一会话多次讲解 → 每次各生成一份（每一次讲解都留存）。"""
    orch = _orchestrator(tmp_path)
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "search_knowledge", "arguments": {"query": "一五计划"}}]
    )
    orch.handle_user_message("u1", "s1", "给我讲讲一五计划")
    orch._concierge = _canned_concierge(
        lambda: [{"id": "t1", "name": "search_knowledge", "arguments": {"query": "园林构景"}}],
        final_text="中国古典园林的构景手法主要有借景、对景、框景、漏景等，"
                   "核心是让有限的园子产生无限的空间感，这是中国园林的独特智慧。",
    )
    orch.handle_user_message("u1", "s1", "园林的构景手法有哪些？")
    assets = _lecture_assets(orch, "u1")
    assert len(assets) == 2, f"两次讲解应各存一份，实际 {len(assets)}"
