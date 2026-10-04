"""知识库目录组织 — 面向浏览与学习的树结构与章节导览。

将 `master_knowledge_base.json` 的原始树转换为前端可直接渲染的紧凑目录树，
并为每个章/节生成「学习导览」（技能点清单、难度分布、对应题数）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from brain_of_cloud.knowledge.loader import KnowledgeBase, Skill


def _leaf_skill(skill: Skill) -> dict[str, Any]:
    return {
        "id": skill.id,
        "type": "skill",
        "title": skill.title,
        "difficulty": skill.difficulty,
        "categories": list(skill.categories),
        "status": skill.status,
        "question_count": 0,  # 由调用方回填
    }


def build_tree(kb: KnowledgeBase, question_counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """构建紧凑目录树：book → (part) → chapter → section → skill。"""
    counts = question_counts or _question_counts_by_skill(kb)
    id2skill = kb.skills_by_id

    def section_node(section: dict[str, Any]) -> dict[str, Any]:
        skills = []
        for child in section.get("children") or []:
            if child["type"] != "skill":
                continue
            s = id2skill.get(child["id"])
            if s is None:
                continue
            node = _leaf_skill(s)
            node["question_count"] = counts.get(s.id, 0)
            skills.append(node)
        return {
            "id": section["id"],
            "type": "section",
            "title": section["title"],
            "children": skills,
        }

    def chapter_node(chapter: dict[str, Any]) -> dict[str, Any]:
        sections = []
        for child in chapter.get("children") or []:
            if child["type"] == "section":
                sections.append(section_node(child))
        return {
            "id": chapter["id"],
            "type": "chapter",
            "title": chapter["title"],
            "children": sections,
            "stats": {
                "sections": len(sections),
                "skills": sum(len(s["children"]) for s in sections),
            },
        }

    def part_node(part: dict[str, Any]) -> dict[str, Any]:
        chapters = []
        for child in part.get("children") or []:
            if child["type"] == "chapter":
                chapters.append(chapter_node(child))
        return {
            "id": part["id"],
            "type": "part",
            "title": part["title"],
            "children": chapters,
            "stats": {
                "chapters": len(chapters),
                "skills": sum(c["stats"]["skills"] for c in chapters),
            },
        }

    books = []
    for book in kb.books:
        children = []
        for child in book.get("children") or []:
            if child["type"] == "part":
                children.append(part_node(child))
            elif child["type"] == "chapter":
                children.append(chapter_node(child))
        books.append(
            {
                "id": book["id"],
                "type": "book",
                "title": book["title"],
                "stats": dict(book.get("stats") or {}),
                "children": children,
            }
        )
    return books


def _question_counts_by_skill(kb: KnowledgeBase) -> dict[str, int]:
    counts: dict[str, int] = {}
    for q in kb.questions:
        if q.skill_id:
            counts[q.skill_id] = counts.get(q.skill_id, 0) + 1
    return counts


@dataclass
class ChapterGuide:
    """一章的学习导览。"""

    book_title: str
    chapter_id: str
    chapter_title: str
    skills: list[Skill] = field(default_factory=list)
    question_count: int = 0

    @property
    def skill_count(self) -> int:
        return len(self.skills)

    @property
    def difficulty_distribution(self) -> dict[int, int]:
        dist: dict[int, int] = {}
        for s in self.skills:
            dist[s.difficulty] = dist.get(s.difficulty, 0) + 1
        return dict(sorted(dist.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "book_title": self.book_title,
            "chapter_id": self.chapter_id,
            "chapter_title": self.chapter_title,
            "skill_count": len(self.skills),
            "question_count": self.question_count,
            "difficulty_distribution": self.difficulty_distribution,
            "skills": [
                {
                    "id": s.id,
                    "title": s.title,
                    "difficulty": s.difficulty,
                    "categories": list(s.categories),
                }
                for s in self.skills
            ],
        }


def build_chapter_guides(kb: KnowledgeBase) -> list[ChapterGuide]:
    """按书/章聚合技能点，生成学习导览。"""
    from collections import defaultdict

    by_key: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"skills": [], "questions": 0}
    )
    for s in kb.skills:
        key = (s.book_title, s.chapter_id)
        by_key[key]["skills"].append(s)
    counts = _question_counts_by_skill(kb)
    for s in kb.skills:
        key = (s.book_title, s.chapter_id)
        by_key[key]["questions"] += counts.get(s.id, 0)

    guides: list[ChapterGuide] = []
    for (book, chapter_id), data in sorted(by_key.items()):
        skills = data["skills"]
        guides.append(
            ChapterGuide(
                book_title=book,
                chapter_id=chapter_id,
                chapter_title=skills[0].chapter_title if skills else chapter_id,
                skills=sorted(skills, key=lambda s: s.id),
                question_count=data["questions"],
            )
        )
    return guides
