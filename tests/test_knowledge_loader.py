"""Tests for the knowledge base loader."""

import json
import re
from pathlib import Path

import pytest

from brain_of_cloud.knowledge.loader import BankQuestion, KnowledgeBaseLoader

_PREFIX_RE = re.compile(r"^[A-Da-d][.、．]")


@pytest.fixture(scope="module")
def kb():
    """Load the real knowledge base once for the whole module."""
    loader = KnowledgeBaseLoader()
    return loader.load()


def test_loads_all_skills(kb):
    assert len(kb.skills) == 3796  # 2026-09-05 并入 0.1.0 领域库(+474)
    assert len(kb.skills_by_id) == 3796


def test_four_books(kb):
    titles = [b["title"] for b in kb.books]
    assert "全国导游基础知识" in titles
    assert "导游业务" in titles
    assert "政策与法律法规" in titles
    assert "地方导游基础知识" in titles


def test_book_stats_match(kb):
    by_title = {b["title"]: b for b in kb.books}
    stats = by_title["全国导游基础知识"]["stats"]
    assert stats["skills"] == 199
    assert stats["chapters"] == 11
    # flat skills count per book
    per_book = sum(1 for s in kb.skills if s.book_title == "全国导游基础知识")
    assert per_book == stats["skills"]


def test_every_skill_has_parent_context(kb):
    for s in kb.skills:
        assert s.book_id and s.book_title, f"skill {s.id} missing book context"
        assert s.path_titles, f"skill {s.id} missing ancestor chain"
        # path_titles 是祖先标题链：[书, (篇), 章, 节]，末位是节（或章）
        assert s.path_titles[-1] in {s.section_title, s.chapter_title}
        assert s.path_titles[0] == s.book_title


def test_skill_fields(kb):
    s = kb.skills_by_id["b01__skill_00001"]
    assert s.title == "“一五”计划的顺利实施"
    assert s.difficulty >= 1
    assert s.categories
    assert s.keywords
    assert len(s.content) > 100
    assert s.parent_id


def test_questions_loaded(kb):
    assert len(kb.questions) == 30944  # 2026-09-05 新增 474 点各 8 题


def test_every_question_maps_to_skill(kb):
    unmapped = [q for q in kb.questions if q.skill_id is None]
    assert not unmapped, f"{len(unmapped)} questions unmapped: {[q.location for q in unmapped[:5]]}"


def test_questions_carry_full_data(kb):
    q = kb.questions[0]
    assert isinstance(q, BankQuestion)
    assert len(q.options) >= 4
    assert q.answer in {"A", "B", "C", "D"}
    assert q.explanation
    assert q.skill_id in kb.skills_by_id


def test_all_question_options_have_letter_prefixes(kb):
    """加载后每个选项都必须带 A./B./C./D. 字母前缀，且与位置一致。

    原始题库 611/713 道题的选项无字母前缀（纯文本），但前端判分与
    展示均按字母前缀工作，因此加载时必须统一规范化。
    """
    unprefixed = []
    wrong_position = []
    for q in kb.questions:
        for i, opt in enumerate(q.options):
            if not _PREFIX_RE.match(opt):
                unprefixed.append((q.answer, opt))
                continue
            expected = chr(65 + i)
            if opt[0].upper() != expected:
                wrong_position.append((opt[:12], expected))
    assert not unprefixed, f"{len(unprefixed)} options still lack A-D prefix: {unprefixed[:3]}"
    assert not wrong_position, f"prefix/position mismatch: {wrong_position[:3]}"


def test_existing_prefixes_are_preserved(kb):
    """原本就带 A./B. 前缀的选项保持原样，不做重复前缀。"""
    q = kb.questions[0]
    assert q.options[0] == "A. 1950～1954年"
    assert q.options[1] == "B. 1953～1957年"


def test_no_prefix_options_get_positional_prefix(kb):
    """原本无前缀的选项按位置补上 A/B/C/D 前缀（如「成渝铁路」题）。"""
    q = kb.questions[4]  # 新中国成立后建成的第一条铁路
    assert q.options == ["A. 成渝铁路", "B. 宝成铁路", "C. 成昆铁路", "D. 青藏铁路"]


def test_questions_grouped_by_skill(kb):
    # every mapped question appears in its skill's group
    for q in kb.questions[:100]:
        assert q.skill_id in kb.questions_by_skill_id
        assert q in kb.questions_by_skill_id[q.skill_id]


def test_difficulty_distribution(kb):
    diffs = {s.difficulty for s in kb.skills}
    assert diffs <= {1, 2, 3, 4, 5}
    assert 3 in diffs


def test_tree_structure_browsable(kb):
    # books expose chapter/section/skill counts
    b = kb.books[0]
    assert b["type"] == "book"
    assert b["children"]
    assert b["stats"]["skills"] > 0


def test_custom_data_dir():
    loader = KnowledgeBaseLoader(data_dir=Path("nonexistent"))
    with pytest.raises(FileNotFoundError):
        loader.load()


def test_question_bank_file_invalid_ignored_when_missing(monkeypatch, tmp_path):
    # Simulate missing question bank -> still loads KB, questions empty
    import shutil
    from pathlib import Path as P

    src = P("data")
    (tmp_path / "master_knowledge_base.json").write_bytes((src / "master_knowledge_base.json").read_bytes())
    loader = KnowledgeBaseLoader(data_dir=tmp_path)
    kb = loader.load()
    assert len(kb.skills) == 3796  # 2026-09-05 并入 0.1.0 领域库(+474)


def test_question_with_slash_in_skill_title_maps(kb):
    """章-节-点 末段含 / 的技能点（如「美国：Mr./Ms.与尊称」）应正确映射，不被 split('/') 切开。"""
    loader = KnowledgeBaseLoader()
    item = {
        "题目": "在美国社交场合中，对成年女性最稳妥的通用称谓是？",
        "选项": ["Miss", "Ms.", "Mrs.", "Lady"],
        "章-节-点": "文化习惯知识 / 美国 / 社交礼仪 / 称呼与称谓 / 美国：Mr./Ms.与尊称",
        "答案": "B",
        "解析": "Ms. 适用于所有成年女性。",
    }
    q = loader._to_bank_question(item, kb.skills_by_title)
    assert q.skill_id is not None
    assert q.skill_title == "美国：Mr./Ms.与尊称"
