"""中文混合检索引擎 — 零外部依赖。

对中文检索，采用「字符二元组(Bigram) BM25」基线 + 三重加权：
1. 标题大词频（×5）
2. 技能点自带 keywords 大词频（×3）
3. 正文大词频（×1）

外加两个强信号：
- 精确关键词命中（查询包含某 skill 的 keyword）→ 大加分
- 标题命中（查询与标题互为子串）→ 加分

这些信号对导游教材这类「标题/关键词表意清晰」的内容非常有效，
且完全可离线、可测试、可复现。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from brain_of_cloud.knowledge.loader import KnowledgeBase, Skill


@dataclass(frozen=True)
class SearchResult:
    skill: Skill
    score: float

    @property
    def id(self) -> str:
        return self.skill.id


_CJK_RE = re.compile(r"[一-鿿]")
_ALNUM_RE = re.compile(r"[a-zA-Z0-9]+")
_LATIN_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "into",
    "are", "you", "your", "what", "how", "which", "where", "when",
}


def tokenize(text: str) -> list[str]:
    """将文本拆分为检索词：CJK 二元组 + 拉丁/数字单词。"""
    tokens: list[str] = []
    cjk = "".join(_CJK_RE.findall(text))
    if len(cjk) >= 2:
        tokens.extend(cjk[i : i + 2] for i in range(len(cjk) - 1))
    if len(cjk) == 1:
        tokens.append(cjk)
    for word in _ALNUM_RE.findall(text.lower()):
        if word not in _LATIN_STOP and len(word) >= 2:
            tokens.append(word)
    return tokens


class ChineseSearchIndex:
    """基于给定知识库构建的内存检索索引。"""

    K1 = 1.5
    B = 0.75
    TITLE_WEIGHT = 5.0
    KEYWORD_WEIGHT = 3.0
    CONTENT_WEIGHT = 1.0
    KEYWORD_HIT_BOOST = 6.0
    TITLE_HIT_BOOST = 4.0
    EXACT_TITLE_BOOST = 50.0

    def __init__(self, kb: KnowledgeBase) -> None:
        self._kb = kb
        self._doc_terms: dict[str, Counter[str]] = {}
        self._doc_len: dict[str, int] = {}
        self._df: Counter[str] = Counter()
        self._build()

    # ---- build ----

    def _build(self) -> None:
        for skill in self._kb.skills:
            terms = self._doc_terms_for_skill(skill)
            self._doc_terms[skill.id] = terms
            self._doc_len[skill.id] = sum(terms.values())
            for term in terms:
                self._df[term] += 1
        total = sum(self._doc_len.values())
        self._avgdl = total / max(len(self._doc_len), 1)

    def _doc_terms_for_skill(self, skill: Skill) -> Counter[str]:
        weighted_bag: list[str] = []
        title_terms = tokenize(skill.title)
        keyword_terms: list[str] = []
        for kw in skill.keywords:
            keyword_terms.extend(tokenize(kw))
        content_terms = tokenize(skill.content)

        weighted_bag.extend(title_terms * int(self.TITLE_WEIGHT))
        weighted_bag.extend(keyword_terms * int(self.KEYWORD_WEIGHT))
        weighted_bag.extend(content_terms)
        return Counter(weighted_bag)

    # ---- query ----

    def search(
        self,
        query: str,
        *,
        knowledge_point_ids: list[str] | None = None,
        book: str | None = None,
        chapter: str | None = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """检索知识库。支持按技能点 ID / 书名 / 章名过滤。"""
        allowed_ids: set[str] | None = None
        if knowledge_point_ids:
            allowed_ids = set(knowledge_point_ids)

        candidates = self._kb.skills
        if allowed_ids is not None:
            candidates = [s for s in candidates if s.id in allowed_ids]
        if book:
            candidates = [s for s in candidates if s.book_title == book]
        if chapter:
            candidates = [
                s for s in candidates
                if s.chapter_title == chapter or s.part_title == chapter
            ]

        if not candidates:
            return []
        if not query.strip():
            return self._fallback(candidates, top_k)

        query_terms = tokenize(query)
        if not query_terms:
            return self._fallback(candidates, top_k)

        # 标题命中 + 关键词命中 的强信号
        query_lower = query.lower().replace(" ", "")
        results: list[SearchResult] = []
        for skill in candidates:
            score = self._bm25_score(skill, query_terms)
            score += self._title_boost(skill, query_lower, query_terms)
            score += self._keyword_boost(skill, query_lower)
            if score > 0:
                results.append(SearchResult(skill=skill, score=score))

        results.sort(key=lambda r: (-r.score, r.skill.difficulty, r.skill.id))
        return results[: max(top_k, 0)]

    def _bm25_score(self, skill: Skill, query_terms: list[str]) -> float:
        terms = self._doc_terms[skill.id]
        dl = self._doc_len[skill.id]
        n = len(self._doc_terms)
        denom = dl + self.K1 * (1 - self.B + self.B * dl / max(self._avgdl, 1))
        total = 0.0
        for term in set(query_terms):
            tf = terms.get(term, 0)
            if tf == 0:
                continue
            df = self._df.get(term, 0)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            total += idf * (tf * (self.K1 + 1)) / (tf + denom)
        return total

    def _title_boost(self, skill: Skill, query_lower: str, query_terms: list[str]) -> float:
        title = skill.title.lower().replace(" ", "")
        boost = 0.0
        if not title:
            return boost
        if title == query_lower:
            boost += self.EXACT_TITLE_BOOST
        elif title in query_lower or query_lower in title:
            boost += self.TITLE_HIT_BOOST
        # 标题 bigram 重叠
        title_terms = set(tokenize(skill.title))
        overlap = len(title_terms & set(query_terms))
        boost += overlap * 0.5
        return boost

    def _keyword_boost(self, skill: Skill, query_lower: str) -> float:
        boost = 0.0
        for kw in skill.keywords:
            kw_lower = kw.lower().replace(" ", "")
            if len(kw_lower) >= 2 and kw_lower in query_lower:
                boost += self.KEYWORD_HIT_BOOST
        return boost

    def _fallback(self, candidates: Iterable[Skill], top_k: int) -> list[SearchResult]:
        """空查询时的保底排序：按技能点优先级（难度低优先、ID 稳定）。"""
        results = [
            SearchResult(skill=s, score=100.0 - s.difficulty)
            for s in candidates
        ]
        results.sort(key=lambda r: (-r.score, r.skill.id))
        return results[: max(top_k, 0)]

    # ---- accessors ----

    @property
    def knowledge_base(self) -> KnowledgeBase:
        return self._kb

    def get_skill(self, skill_id: str) -> Skill | None:
        return self._kb.skills_by_id.get(skill_id)

    def get_question(self, question_id: str) -> object | None:
        """按 question_id 查题（question_id 由插件生成，此处按索引顺序）。"""
        try:
            idx = int(question_id.rsplit("_", 1)[-1])
            return self._kb.questions[idx] if 0 <= idx < len(self._kb.questions) else None
        except (ValueError, IndexError):
            return None
