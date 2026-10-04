"""会话上下文管理服务（T7 / D-26）— 长对话摘要与 token 预算控制。

设计（docs/context-management-design-2026-08-29.md）：
- 保留最近 MAX_KEEP_MESSAGES 条完整消息；更早的消息在超阈值后压缩为「早前对话摘要」
- 摘要惰性触发：最早溢出段字符超 TRIGGER_CHARS 才首次生成；距上次摘要新增 ≥REFRESH_STEP 条才增量重摘要
- 摘要注入为 system 消息，位于保留窗口之前；对用户不可见，管家据此衔接旧话题
"""

from __future__ import annotations

from typing import Any, Protocol


class LLMClientLike(Protocol):
    model: str

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str: ...


SUMMARY_SYSTEM_PROMPT = """\
你是对话上下文压缩器。把一段较长的「早前对话」压缩成不超过 300 字的中文摘要，
供后续对话参考。必须保留以下信息（按重要性）：
1. 学员身份与背景信息（姓名/专业/目标/时间安排）
2. 正在学习/已学过的主题与进度（讲到哪了）
3. 答题情况（对错、薄弱点、连续对错）
4. 学员明确提出的要求、偏好或待办事项
5. 双方约定了但还没做完的事（如"明天继续讲X"）

要求：
- 只压缩原文事实，禁止编造原文没有的信息
- 用简洁条目式中文，不要客套话
- 如果提供了「旧摘要」，把它与新消息合并压缩，避免信息丢失"""


class ConversationContextManager:
    """纯函数 + LLM 惰性触发的会话上下文裁剪。"""

    MAX_KEEP_MESSAGES = 24          # 保留最近 N 条完整消息
    TRIGGER_CHARS = 8000            # 溢出段字符超此值才首次摘要
    REFRESH_STEP = 8                # 距上次摘要新增 ≥N 条才重摘要

    def __init__(
        self,
        llm: LLMClientLike | None = None,
        *,
        max_keep: int | None = None,
        trigger_chars: int | None = None,
        refresh_step: int | None = None,
    ) -> None:
        self._llm = llm
        if max_keep is not None:
            self.MAX_KEEP_MESSAGES = max_keep
        if trigger_chars is not None:
            self.TRIGGER_CHARS = trigger_chars
        if refresh_step is not None:
            self.REFRESH_STEP = refresh_step

    # ---- 判定（纯函数，可单测） ----

    def overflow_count(self, history: list[dict[str, Any]]) -> int:
        """超出保留窗口的消息条数（窗口内不摘要）。"""
        return max(0, len(history) - self.MAX_KEEP_MESSAGES)

    def should_summarize(
        self,
        history: list[dict[str, Any]],
        existing_summary: str | None,
        last_message_count: int,
    ) -> bool:
        """是否需要生成/更新摘要。"""
        overflow = self.overflow_count(history)
        if overflow <= 0:
            return False
        if existing_summary is None:
            # 首次：溢出段字符达到阈值才摘要（短会话不摘要）
            overflow_chars = sum(
                len(str(m.get("content") or "")) for m in history[:overflow]
            )
            return overflow_chars >= self.TRIGGER_CHARS
        # 已有摘要：距上次摘要新增 ≥ REFRESH_STEP 条才增量重摘要
        return len(history) - last_message_count >= self.REFRESH_STEP

    def apply(
        self,
        history: list[dict[str, Any]],
        summary: str,
    ) -> list[dict[str, Any]]:
        """把摘要 + 保留窗口拼成新历史（摘要作为 system 消息）。"""
        keep = history[-self.MAX_KEEP_MESSAGES:]
        return [
            {
                "role": "system",
                "content": f"【早前对话摘要（{len(history) - len(keep)} 条消息已压缩）】{summary}",
            },
            *keep,
        ]

    def _render_overflow(self, history: list[dict[str, Any]]) -> str:
        overflow = history[:-self.MAX_KEEP_MESSAGES] if len(history) > self.MAX_KEEP_MESSAGES else history
        lines = []
        for m in overflow:
            role = m.get("role", "")
            content = str(m.get("content") or "").strip()
            if role == "tool":
                lines.append(f"[工具结果] {content[:120]}")
            elif role == "assistant":
                lines.append(f"[管家] {content[:200]}")
            else:
                lines.append(f"[学员] {content[:200]}")
        return "\n".join(lines)

    def summarize(
        self,
        history: list[dict[str, Any]],
        existing_summary: str | None = None,
    ) -> str:
        """调 LLM 生成/增量更新摘要。

        失败兜底：LLM 不可用/异常/空结果时返回「规则临时摘要」（截取溢出段关键内容），
        保证长会话不丢上下文；LLM 恢复后下一次增量触发会用优质摘要替换它。
        """
        if self._llm is None:
            return existing_summary or self._fallback_summary(history)
        overflow_text = self._render_overflow(history)
        user_prompt = f"旧摘要（如有）：\n{existing_summary or '（无）'}\n\n需要压缩的新对话内容：\n{overflow_text}"
        try:
            resp = self._llm.chat(
                [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=500,
                temperature=0.3,
            )
            content = getattr(resp, "content", resp)
            content = (content or "").strip()
        except Exception:
            content = ""
        if not content or len(content) < 10:
            # LLM 失败/空结果 → 规则兜底
            return existing_summary or self._fallback_summary(history)
        return content

    def _fallback_summary(self, history: list[dict[str, Any]]) -> str:
        """规则临时摘要：溢出段每条消息取关键片段拼接（LLM 不可用时的降级）。"""
        lines = []
        for m in history[: self.MAX_KEEP_MESSAGES]:
            role = "学员" if m.get("role") != "assistant" else "管家"
            snippet = str(m.get("content") or "").strip()[:60]
            if snippet:
                lines.append(f"{role}：{snippet}")
            if len(lines) >= 10:
                break
        head = "（临时摘要，待自动更新）\n" + "\n".join(lines)
        return head
