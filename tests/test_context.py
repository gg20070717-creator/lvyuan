"""会话上下文管理（T7 / D-26）：长对话摘要、保留窗口、token 预算控制。"""
from unittest.mock import MagicMock

from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.context import (
    SUMMARY_SYSTEM_PROMPT,
    ConversationContextManager,
)
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def _mk(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def _history(n: int) -> list[dict[str, str]]:
    return [_mk("user" if i % 2 == 0 else "assistant", f"消息{i}") for i in range(n)]


class TestContextManagerPure:
    """纯函数部分：阈值、窗口、替换逻辑。"""

    def test_no_overflow_returns_false(self):
        mgr = ConversationContextManager(max_keep=4)
        assert mgr.overflow_count(_history(4)) == 0
        assert mgr.should_summarize(_history(4), None, 0) is False

    def test_overflow_without_threshold_chars_no_first_summary(self):
        """溢出但溢出段字符太少 → 不首次摘要（短会话不摘要）。"""
        mgr = ConversationContextManager(max_keep=4, trigger_chars=8000)
        hist = _history(10)  # 溢出 6 条，每条 ~10 字符，远小于 8000
        assert mgr.should_summarize(hist, None, 0) is False

    def test_first_summary_when_overflow_chars_reach_threshold(self):
        mgr = ConversationContextManager(max_keep=4, trigger_chars=50)
        hist = [_mk("user", "很长" * 30) for _ in range(6)]  # 溢出 2 条 × 120 字符
        assert mgr.should_summarize(hist, None, 0) is True

    def test_incremental_refresh_only_after_refresh_step(self):
        mgr = ConversationContextManager(max_keep=4, refresh_step=8)
        hist = _history(10)
        # 已有摘要，距上次 6 条 → 不重摘要
        assert mgr.should_summarize(hist, "旧摘要", 4) is False
        # 距上次 9 条 → 重摘要
        assert mgr.should_summarize(_history(13), "旧摘要", 4) is True

    def test_apply_keeps_window_and_prepends_summary(self):
        mgr = ConversationContextManager(max_keep=4)
        hist = _history(10)
        out = mgr.apply(hist, "压缩摘要")
        assert len(out) == 5
        assert out[0]["role"] == "system"
        assert "早前对话摘要" in out[0]["content"]
        assert "6 条消息已压缩" in out[0]["content"]
        # 保留窗口为最后 4 条，顺序不变
        assert [m["content"] for m in out[1:]] == [f"消息{i}" for i in range(6, 10)]

    def test_summarize_prompt_requires_progress_info(self):
        assert "学习" in SUMMARY_SYSTEM_PROMPT or "进度" in SUMMARY_SYSTEM_PROMPT
        assert "禁止编造" in SUMMARY_SYSTEM_PROMPT

    def test_summarize_llm_failure_falls_back_to_rules(self):
        """LLM 抛异常 → 规则兜底摘要（不丢上下文）。"""
        llm = MagicMock()
        llm.chat.side_effect = RuntimeError("llm down")
        mgr = ConversationContextManager(llm, max_keep=4)
        hist = _history(8)

        s = mgr.summarize(hist)

        assert s.startswith("（临时摘要")
        assert "学员" in s
        assert "消息" in s  # 含原文片段

    def test_summarize_empty_result_falls_back(self):
        """LLM 返回空结果 → 规则兜底摘要。"""
        llm = MagicMock()
        llm.chat.return_value.content = "  "
        mgr = ConversationContextManager(llm, max_keep=4)

        s = mgr.summarize(_history(8))

        assert s.startswith("（临时摘要")

    def test_summarize_short_result_falls_back(self):
        """LLM 返回过短内容（<10 字符，疑似无意义）→ 规则兜底。"""
        llm = MagicMock()
        llm.chat.return_value.content = "（无）"
        mgr = ConversationContextManager(llm, max_keep=4)

        s = mgr.summarize(_history(8))

        assert s.startswith("（临时摘要")

    def test_summarize_success_returns_llm_content(self):
        llm = MagicMock()
        llm.chat.return_value.content = "学员在学园林构景，讲到借景。"
        mgr = ConversationContextManager(llm, max_keep=4)

        s = mgr.summarize(_history(8))

        assert s == "学员在学园林构景，讲到借景。"


class TestContextOrchestrator:
    """orchestrator 集成：超长历史 → conversation 含摘要且最近消息完整。"""

    def _orch(self, tmp_path):
        store = SQLiteStore(tmp_path / "ctx.sqlite")
        store.initialize()
        llm = MagicMock()
        llm.model = "deepseek-v4-pro"
        orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=llm)
        orch._user_id_ctx.set("u1")
        orch._session_id_ctx.set("s1")
        return orch, store, llm

    def test_long_history_gets_summarized_in_conversation(self, tmp_path):
        orch, store, llm = self._orch(tmp_path)
        # 构造 40 条历史消息（溢出 16 条 × ~1400 字符 > 8000 触发阈值）
        for i in range(40):
            store.save_session_message(
                "s1", "u1",
                "user" if i % 2 == 0 else "assistant",
                f"第{i}轮对话内容" + "很长的对话内容" * 200,
            )
        llm.chat.return_value.content = "【真实摘要】学员在学园林构景，讲到借景，答对 3 题。"
        # 捕获管家收到的 conversation（避免真实 LLM 调用）
        from brain_of_cloud.services.agents.concierge import AgentResponse
        think = MagicMock(return_value=AgentResponse(text="好的"))
        orch._concierge.think = think

        result = orch.handle_user_message("u1", "s1", "继续")
        assert result.response  # 正常应答

        # 管家收到的 conversation 中应注入「早前对话摘要」system 消息
        conv = think.call_args.args[0]
        summary_msgs = [m for m in conv if m.get("role") == "system" and "早前对话摘要" in m.get("content", "")]
        assert summary_msgs, "长会话应注入早前对话摘要"
        assert "【真实摘要】" in summary_msgs[0]["content"]
        # 保留窗口：完整消息数 = 最近 24 条 + 本条 user + 最终 assistant 回复
        full_msgs = [m for m in conv if m.get("role") in ("user", "assistant")]
        assert len(full_msgs) == 26

        # 摘要持久化
        row = store.get_session_summary("s1")
        assert row is not None
        assert row["message_count"] == 40

    def test_short_history_no_summary(self, tmp_path):
        orch, store, llm = self._orch(tmp_path)
        for i in range(5):
            store.save_session_message("s1", "u1", "user" if i % 2 == 0 else "assistant", f"短消息{i}")
        from brain_of_cloud.services.agents.concierge import AgentResponse
        orch._concierge.think = MagicMock(return_value=AgentResponse(text="好的"))

        orch.handle_user_message("u1", "s1", "继续")

        assert store.get_session_summary("s1") is None

    def test_summary_deleted_with_user_data(self, tmp_path):
        store = SQLiteStore(tmp_path / "d.sqlite")
        store.initialize()
        store.save_session_summary("s1", "u1", "摘要", 30)

        store.delete_user_data("u1", InboundGuidePlugin().manifest["plugin_id"])

        assert store.get_session_summary("s1") is None

    def test_clear_session_removes_summary(self, tmp_path):
        orch, store, llm = self._orch(tmp_path)
        store.save_session_summary("s1", "u1", "摘要", 30)

        orch.clear_session("s1")

        assert store.get_session_summary("s1") is None
