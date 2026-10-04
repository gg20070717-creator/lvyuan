"""导游资格证备考训练插件 — 由真实知识库（3796 技能点）+ 题库（30944 题）驱动。

实现了与 InboundGuidePlugin 相同的插件接口（search / questions / list_knowledge_points），
因此可无缝替换旧插件接入 Orchestrator 与 TrainingService。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from brain_of_cloud.domain.models import Evidence, KnowledgePoint, Question
from brain_of_cloud.knowledge import KnowledgeBase, KnowledgeBaseLoader
from brain_of_cloud.knowledge.loader import BankQuestion, Skill
from brain_of_cloud.knowledge.search import ChineseSearchIndex

_DIFF_MAP = {
    1: "intro",
    2: "intro",
    3: "basic",
    4: "advanced",
    5: "comprehensive",
}
_INT_DIFF = {v: k for k, v in _DIFF_MAP.items()}


class TourGuidePlugin:
    manifest = {
        "plugin_id": "tour_guide_exam",
        "name": "导游资格证备考训练",
        "version": "1.0.0",
        "training_provider": "全国导游教材 + 跨文化 + 入境游实战 + 真实岗位实务 + 旅游定制师 + 入境游接待（3796 技能点 / 30944 题）",
        "supported_assets": ["lecture", "practice_guide", "graded_quiz", "text"],
    }

    def __init__(
        self,
        loader: KnowledgeBaseLoader | None = None,
    ) -> None:
        self._kb: KnowledgeBase = (loader or KnowledgeBaseLoader()).load()
        self._index = ChineseSearchIndex(self._kb)
        self._questions: list[Question] = [
            self._to_question(q, i)
            for i, q in enumerate(self._kb.questions)
        ]

    # ---- 知识库访问 ----

    @property
    def knowledge_base(self) -> KnowledgeBase:
        return self._kb

    def get_skill(self, skill_id: str) -> Skill | None:
        return self._kb.skills_by_id.get(skill_id)

    def get_skill_by_title(self, title: str) -> Skill | None:
        hits = self._kb.skills_by_title.get(title) or []
        return hits[0] if hits else None

    def list_books(self) -> list[dict[str, Any]]:
        return self._kb.books

    def get_book(self, book_id: str) -> dict[str, Any] | None:
        for b in self._kb.books:
            if b["id"] == book_id:
                return b
        return None

    def stats(self) -> dict[str, int]:
        return self._kb.stats

    # ---- 插件接口 ----

    def list_knowledge_points(self) -> list[KnowledgePoint]:
        return [
            KnowledgePoint(
                id=s.id,
                name=s.title,
                level=_DIFF_MAP.get(s.difficulty, "basic"),
                prerequisites=list(s.dependencies),
                target_skill=s.content[:80],
            )
            for s in self._kb.skills
        ]

    def search(
        self,
        query: str,
        knowledge_point_ids: list[str] | None = None,
        top_k: int = 5,
    ) -> list[Evidence]:
        results = self._index.search(
            query,
            knowledge_point_ids=knowledge_point_ids or [],
            top_k=max(top_k, 3),
        )
        evidence: list[Evidence] = []
        for r in results:
            s = r.skill
            evidence.append(
                Evidence(
                    chunk_id=s.id,
                    content=s.content,
                    source=self._source_str(s),
                    trust_score=min(max(r.score / 40.0, 0.5), 0.98),
                    knowledge_point_ids=[s.id],
                )
            )
        return evidence

    def questions(self, knowledge_point_ids: list[str] | None = None) -> list[Question]:
        allowed = set(knowledge_point_ids or [])
        if not allowed:
            return list(self._questions)
        return [q for q in self._questions if q.knowledge_point_id in allowed]

    def questions_filtered(
        self,
        *,
        knowledge_point_ids: list[str] | None = None,
        book: str | None = None,
        chapter: str | None = None,
        difficulty: str | None = None,
        limit: int | None = None,
        exclude_answered: set[str] | None = None,
    ) -> list[Question]:
        """灵活筛选题库，供出题与前端浏览使用。"""
        out = [q for q in self._questions if q.options]  # 选择题池：排除简答（无选项）
        if knowledge_point_ids:
            allowed = set(knowledge_point_ids)
            out = [q for q in out if q.knowledge_point_id in allowed]
        if book:
            out = [q for q in out if self._book_of(q) == book]
        if chapter:
            out = [
                q for q in out
                if self._chapter_of(q) == chapter
            ]
        if difficulty:
            out = [q for q in out if q.difficulty == difficulty]
        if exclude_answered:
            out = [q for q in out if q.question_id not in exclude_answered]
        if limit is not None:
            out = out[:limit]
        return out

    def random_questions(
        self,
        n: int = 5,
        *,
        knowledge_point_ids: list[str] | None = None,
        exclude_answered: set[str] | None = None,
        difficulty: str | None = None,
        book: str | None = None,
        chapter: str | None = None,
    ) -> list[Question]:
        """随机抽取 n 道题（确定性种子，便于测试）。"""
        import random

        pool = self.questions_filtered(
            knowledge_point_ids=knowledge_point_ids,
            difficulty=difficulty,
            exclude_answered=exclude_answered,
            book=book,
            chapter=chapter,
        )
        if not pool:
            return []
        rng = random.Random(42)
        return rng.sample(pool, min(n, len(pool)))

    def get_question(self, question_id: str) -> Question | None:
        for q in self._questions:
            if q.question_id == question_id:
                return q
        return None

    # ---- 转换辅助 ----

    def _to_question(self, bq: BankQuestion, idx: int) -> Question:
        skill = self._kb.skills_by_id.get(bq.skill_id or "")
        diff = _DIFF_MAP.get(bq.difficulty or 3, "basic")
        if bq.qtype == "简答":
            return Question(
                question_id=f"q_{idx:05d}",
                knowledge_point_id=bq.skill_id or "",
                difficulty=diff,
                difficulty_level=bq.difficulty,
                prompt=bq.question,
                answer_key=bq.explanation or bq.answer,
                rubric=bq.answer,
                options=[],
                answer="",
                explanation=bq.explanation or "",
                source=bq.location,
            )
        return Question(
            question_id=f"q_{idx:05d}",
            knowledge_point_id=bq.skill_id or "",
            difficulty=diff,
                difficulty_level=bq.difficulty,
            prompt=bq.question,
            answer_key=bq.explanation,
            options=list(bq.options),
            answer=bq.answer.strip().upper(),
            explanation=bq.explanation,
            source=bq.location,
            misconception_tags=self._misconception_tags(bq),
        )

    def _misconception_tags(self, bq: BankQuestion) -> list[str]:
        tags = []
        if bq.answer and len(bq.answer) == 1:
            tags.append(f"ans_{bq.answer}")
        if "罚款" in bq.question or "处罚" in bq.question:
            tags.append("penalty")
        if bq.skill_id:
            skill = self._kb.skills_by_id.get(bq.skill_id)
            if skill and "法规" in skill.categories:
                tags.append("regulation")
        return tags

    def _source_str(self, skill: Skill) -> str:
        parts = [skill.book_title]
        if skill.part_title:
            parts.append(skill.part_title)
        parts.extend([skill.chapter_title, skill.section_title])
        return " / ".join(parts)

    def _book_of(self, q: Question) -> str:
        parts = [p.strip() for p in (q.source or "").split("/") if p.strip()]
        return parts[0] if parts else ""

    def _chapter_of(self, q: Question) -> str:
        parts = [p.strip() for p in (q.source or "").split("/") if p.strip()]
        return parts[1] if len(parts) > 1 else ""
