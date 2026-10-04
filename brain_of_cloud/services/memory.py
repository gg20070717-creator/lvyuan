"""用户长期记忆服务 — 跨会话记住每个学员的背景、目标与偏好。

记忆来源：
1. 画像生成（update_profile）→ 结构化事实
2. 对话中规则提取（我叫/我是/我的目标/我想/我喜欢...）
3. 学习行为（薄弱点）→ 由调用方写入

记忆注入：每次管家对话前把「学员档案 + 最近记忆 + 薄弱点」拼成上下文块，
让管家真正按每个用户定制回复。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from brain_of_cloud.storage.sqlite import SQLiteStore

_MEMORY_TYPE_LABELS = {
    "fact": "学员信息",
    "goal": "学习目标",
    "preference": "学习偏好",
    "background": "背景",
    "progress_note": "学习记录",
}

# 中文口语提取规则：(正则, 记忆类型, 模板)
_EXTRACT_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"我(?:叫|是)\s*([一-鿿A-Za-z]{1,12})"), "fact", "学员名叫「{0}」"),
    (re.compile(r"(?:我的)?目标(?:是|就是)?\s*([^\s，。！？,.]+)"), "goal", "学习目标：{0}"),
    (re.compile(r"(?:我)?想(?:考|报考|通过)\s*([^\s，。！？,.]+)"), "goal", "想考取：{0}"),
    (re.compile(r"(?:我)?正在(?:备考|准备|复习)\s*([^\s，。！？,.]+)"), "background", "正在备考：{0}"),
    (re.compile(r"(?:我)?(?:喜欢|偏好|偏爱)\s*([^\s，。！？,.]+)"), "preference", "学习偏好：{0}"),
    (re.compile(r"我(?:是|在读)\s*([^\s，。！？,.]+(?:专业|大学|学院|学生|老师|工作))"), "background", "背景：{0}"),
    (re.compile(r"我(?:已经|以前|之前)(?:学过|背过|考过)\s*([^\s，。！？,.]+)"), "background", "已有基础：{0}"),
    (re.compile(r"(?:我)?(?:感觉|觉得|认为)(?:自己)?\s*([^\s，。！？,.]+(?:弱|薄弱|差|不好))"), "progress_note", "自评薄弱：{0}"),
]


@dataclass(frozen=True)
class MemoryExtractResult:
    memories: list[dict[str, object]]


class UserMemoryService:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self._store = store

    # ---- 写入 ----

    def add_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        importance: float = 0.6,
        source_session: str | None = None,
    ) -> None:
        if not self._store:
            return
        self._store.save_memory(
            memory_id=f"mem_{uuid4().hex[:12]}",
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            source_session=source_session,
        )

    # ---- 读取 ----

    def list_memories(self, user_id: str, limit: int = 20) -> list[dict[str, object]]:
        if not self._store:
            return []
        return self._store.get_memories(user_id, limit=limit)

    # ---- 从对话中提取 ----

    def extract_from_message(
        self,
        user_id: str,
        session_id: str,
        text: str,
    ) -> list[dict[str, object]]:
        """规则提取学员自述中的持久事实，去重后写入记忆库。"""
        if not self._store or not text:
            return []
        existing = {
            m["content"] for m in self._store.get_memories(user_id, limit=200)
        }
        extracted: list[dict[str, object]] = []
        for pattern, mtype, template in _EXTRACT_RULES:
            match = pattern.search(text)
            if not match:
                continue
            value = match.group(1).strip()
            if not value or len(value) < 2:
                continue
            content = template.format(value)
            if content in existing:
                continue
            self._store.save_memory(
                memory_id=f"mem_{uuid4().hex[:12]}",
                user_id=user_id,
                memory_type=mtype,
                content=content,
                importance=self._importance(mtype),
                source_session=session_id,
            )
            existing.add(content)
            extracted.append({"memory_type": mtype, "content": content})
        return extracted

    # ---- 用户上下文块（注入管家） ----

    def build_user_context(
        self,
        user_id: str,
        *,
        profile=None,
        weak_points: list[str] | None = None,
        weak_point_titles: list[str] | None = None,
        memory_limit: int = 8,
    ) -> str:
        """组装一段中文「学员档案」上下文，供注入管家对话。"""
        lines: list[str] = ["【学员档案 - 供你个性化辅导，别在回复里原样复述这些信息】"]
        if profile is not None:
            lines.append(
                f"目标岗位：{getattr(profile, 'target_role', '未设定') or '未设定'}"
            )
            lines.append(
                f"当前等级：{getattr(profile, 'current_level', 'intro') or 'intro'}"
            )
            bg = getattr(profile, "background", "") or ""
            if bg:
                lines.append(f"背景：{bg[:120]}")
            styles = getattr(profile, "style_preferences", {}) or {}
            if styles.get("mode"):
                lines.append(f"学习风格：{styles['mode']}")

        memories = self.list_memories(user_id, limit=memory_limit)
        if memories:
            lines.append(
                "该学员此前的记录："
                + "；".join(
                    f"[{_MEMORY_TYPE_LABELS.get(str(m['memory_type']), str(m['memory_type']))}] {m['content']}"
                    for m in memories
                )
            )

        if weak_point_titles:
            shown = weak_point_titles[:6]
            lines.append(f"当前薄弱知识点：{'、'.join(shown)}")

        return "\n".join(lines)

    def _importance(self, memory_type: str) -> float:
        return {
            "goal": 0.9,
            "fact": 0.8,
            "background": 0.7,
            "preference": 0.6,
            "progress_note": 0.5,
        }.get(memory_type, 0.5)
