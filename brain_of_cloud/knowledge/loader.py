"""知识库加载器 — 加载并索引 `data/master_knowledge_base.json` 与题库。

数据格式见 `data/知识库与题库说明.md`。

树结构：master → book → (part) → chapter → section → skill。
`skills[]` 是全部技能点的平铺数组；`root.children` 是树。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# 选项字母前缀：A. / B、 / C． 等（用于识别已有前缀的选项）
_OPTION_PREFIX_RE = re.compile(r"^[A-Da-d][.、．]\s*")


@dataclass(frozen=True)
class Skill:
    """一个技能点（知识单元）。"""

    id: str
    title: str
    content: str
    keywords: list[str]
    categories: list[str]
    difficulty: int
    status: str
    dependencies: list[str]
    parent_id: str | None

    book_id: str
    book_title: str
    part_title: str | None
    chapter_id: str
    chapter_title: str
    section_id: str
    section_title: str
    path_titles: list[str]  # [书, (篇), 章, 节] 的标题链（不含技能点本身）


@dataclass(frozen=True)
class BankQuestion:
    """题库中的一道真题。"""

    question: str  # 题目
    options: list[str]  # 4 个选项（含 A./B. 前缀）
    location: str  # 章-节-点
    answer: str  # 答案字母 A/B/C/D
    explanation: str  # 解析
    skill_id: str | None = None  # 映射到的技能点 ID（加载时解析）
    skill_title: str | None = None
    difficulty: int | None = None  # 取自映射技能点的难度
    qtype: str = "选择"  # 题型：选择 / 判断 / 简答


@dataclass
class KnowledgeBase:
    """加载后的完整知识库。"""

    schema_version: str
    books: list[dict[str, Any]]  # 树形结构（用于浏览）
    skills: list[Skill]
    skills_by_id: dict[str, Skill]
    questions: list[BankQuestion]
    questions_by_skill_id: dict[str, list[BankQuestion]]
    skills_by_title: dict[str, list[Skill]]

    @property
    def stats(self) -> dict[str, int]:
        return {
            "books": len(self.books),
            "skills": len(self.skills),
            "questions": len(self.questions),
        }


class KnowledgeBaseLoader:
    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is None:
            data_dir = os.environ.get("BOC_DATA_DIR") or (
                Path(__file__).resolve().parents[2] / "data"
            )
        self._data_dir = Path(data_dir)

    def load(self) -> KnowledgeBase:
        kb_path = self._data_dir / "master_knowledge_base.json"
        qb_path = self._data_dir / "master_question_bank.json"
        if not kb_path.exists():
            raise FileNotFoundError(f"知识库文件不存在: {kb_path}")

        raw = self._load_json(kb_path)
        schema_version = raw.get("schemaVersion", "unknown")

        # 1. 建立 id → 节点 的索引，并解析每个技能点的上下文
        id2node: dict[str, dict[str, Any]] = {}
        books: list[dict[str, Any]] = []

        def walk(node: dict[str, Any]) -> None:
            id2node[node["id"]] = node
            if node["type"] == "book":
                books.append(node)
            for child in node.get("children") or []:
                walk(child)

        walk(raw["root"])

        # 2. 解析技能点（优先用 skills[] 平铺数组，树用于上下文）
        flat_skills = raw.get("skills") or []
        skills: list[Skill] = []
        skills_by_id: dict[str, Skill] = {}
        skills_by_title: dict[str, list[Skill]] = {}

        for node in flat_skills:
            if node.get("type") != "skill":
                continue
            ctx = self._build_skill_context(node, id2node)
            skill = Skill(
                id=node["id"],
                title=node["title"],
                content=node.get("content", ""),
                keywords=list(node.get("keywords") or []),
                categories=list(node.get("categories") or []),
                difficulty=int(node.get("difficulty", 3)),
                status=node.get("status", "locked"),
                dependencies=list(node.get("dependencies") or []),
                parent_id=node.get("parentId"),
                **ctx,
            )
            skills.append(skill)
            skills_by_id[skill.id] = skill
            skills_by_title.setdefault(skill.title, []).append(skill)

        # 3. 加载题库并映射到技能点（按标题精确匹配，已验证题库题目可全部命中技能点）
        questions: list[BankQuestion] = []
        questions_by_skill_id: dict[str, list[BankQuestion]] = {}
        if qb_path.exists():
            qb_raw = self._load_json(qb_path)
            for item in qb_raw.get("questions") or []:
                q = self._to_bank_question(item, skills_by_title)
                questions.append(q)
                if q.skill_id:
                    questions_by_skill_id.setdefault(q.skill_id, []).append(q)

        return KnowledgeBase(
            schema_version=schema_version,
            books=books,
            skills=skills,
            skills_by_id=skills_by_id,
            questions=questions,
            questions_by_skill_id=questions_by_skill_id,
            skills_by_title=skills_by_title,
        )

    # ---- helpers ----

    def _load_json(self, path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _build_skill_context(
        self,
        node: dict[str, Any],
        id2node: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """沿 parentId 链回溯，提取书/章/节上下文。"""
        book_id = book_title = ""
        part_title: str | None = None
        chapter_id = chapter_title = ""
        section_id = section_title = ""
        path_titles: list[str] = []

        cur: dict[str, Any] | None = node
        seen: set[str] = set()
        # 自底向上收集祖先
        ancestors: list[dict[str, Any]] = []
        while cur is not None and cur["id"] not in seen:
            seen.add(cur["id"])
            pid = cur.get("parentId")
            parent = id2node.get(pid) if pid else None
            if parent is None:
                break
            ancestors.append(parent)
            cur = parent

        # ancestors 自下而上：[section, chapter, part?, book, master]
        for anc in reversed(ancestors):
            t = anc["type"]
            if t == "master":
                continue
            if t == "book":
                book_id, book_title = anc["id"], anc["title"]
            elif t == "part":
                part_title = anc["title"]
            elif t == "chapter":
                chapter_id, chapter_title = anc["id"], anc["title"]
            elif t == "section":
                section_id, section_title = anc["id"], anc["title"]
            path_titles.append(anc["title"])

        return {
            "book_id": book_id,
            "book_title": book_title,
            "part_title": part_title,
            "chapter_id": chapter_id,
            "chapter_title": chapter_title,
            "section_id": section_id,
            "section_title": section_title,
            "path_titles": path_titles,
        }

    def _to_bank_question(
        self,
        item: dict[str, Any],
        skills_by_title: dict[str, list[Skill]],
    ) -> BankQuestion:
        location = item.get("章-节-点", "")
        # 分隔符是「 / 」（带空格）；技能点标题可能含 / （如「美国：Mr./Ms.与尊称」），
        # 因此不能用 split("/")，否则会把标题切开导致映射失败。
        parts = [p.strip() for p in re.split(r"\s+/\s+", location) if p.strip()]
        skill_title = parts[-1] if parts else ""
        skill = skills_by_title.get(skill_title, [None])[0]  # 标题唯一时命中

        # 难度（1-5）：优先取题库「难度」字段，缺失时回退映射技能点难度
        raw_diff = item.get("难度")
        try:
            diff = int(raw_diff)
            if not (1 <= diff <= 5):
                diff = skill.difficulty if skill else 3
        except (TypeError, ValueError):
            diff = skill.difficulty if skill else 3

        raw_opts = list(item.get("选项") or [])
        qtype = str(item.get("类型") or ("判断" if len(raw_opts) == 2 and not _OPTION_PREFIX_RE.match(str(raw_opts[0] or "")) and "正确" in str(raw_opts[0] or "") else ("简答" if not raw_opts else "选择")))

        q = BankQuestion(
            question=item.get("题目", ""),
            options=self._normalize_options(raw_opts),
            location=location,
            answer=item.get("答案", ""),
            explanation=item.get("解析", ""),
            skill_id=skill.id if skill else None,
            skill_title=skill.title if skill else None,
            difficulty=diff,
            qtype=qtype,
        )
        return q

    def _normalize_options(self, options: list[str]) -> list[str]:
        """统一选项为「A. 内容」格式：已有 A-D 字母前缀则保留，否则按位置补前缀。

        题库两种来源格式混杂：102 道选项带 A./B. 前缀，611 道为纯文本选项。
        前端判分、选项字母展示、正确项高亮均按「选项带字母前缀」工作，
        因此加载时统一规范化，保证答案字母与选项位置一致。
        """
        normalized: list[str] = []
        for i, opt in enumerate(options):
            text = (opt or "").strip()
            if _OPTION_PREFIX_RE.match(text):
                normalized.append(text)
            else:
                normalized.append(f"{chr(65 + i)}. {text}")
        return normalized
