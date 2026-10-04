"""Tests for knowledge catalog (tree + chapter guides)."""

import pytest

from brain_of_cloud.knowledge import build_chapter_guides, build_tree
from brain_of_cloud.knowledge.loader import KnowledgeBaseLoader


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBaseLoader().load()


def test_tree_four_books(kb):
    tree = build_tree(kb)
    assert len(tree) == 7  # 2026-09-05 新增 17 本已收纳为 7 大领域下的 part
    titles = {b["title"] for b in tree}
    assert "全国导游基础知识" in titles


def test_tree_book_has_children(kb):
    tree = build_tree(kb)
    guide_book = next(b for b in tree if b["title"] == "全国导游基础知识")
    # 该书无 part，子节点应为章
    assert all(c["type"] == "chapter" for c in guide_book["children"])
    assert guide_book["stats"]["skills"] == 199


def test_tree_with_parts(kb):
    tree = build_tree(kb)
    guide_book = next(b for b in tree if b["title"] == "导游业务")
    # 导游业务有 part
    assert any(c["type"] == "part" for c in guide_book["children"])
    total = sum(
        c["stats"]["skills"] for c in guide_book["children"]
    )
    # 动态：导游业务书（含并入的真实岗位实务 5 part）的实际技能点数
    book_id = next(b["id"] for b in kb.books if b["title"] == "导游业务")
    assert total == sum(1 for s in kb.skills if s.book_id == book_id)


def test_tree_skill_leaf_fields(kb):
    tree = build_tree(kb)
    # 钻取到第一个技能点
    book = tree[0]
    chapter = book["children"][0]
    section = chapter["children"][0]
    skill = section["children"][0]
    assert skill["type"] == "skill"
    assert skill["id"]
    assert skill["title"]
    assert skill["difficulty"] >= 1
    assert skill["question_count"] >= 0


def test_question_counts_backfilled(kb):
    tree = build_tree(kb)
    # 全国导游基础知识全书题目数应 > 0
    book = next(b for b in tree if b["title"] == "全国导游基础知识")
    flat_skills = []

    def walk(node):
        if node["type"] == "skill":
            flat_skills.append(node)
        for c in node.get("children") or []:
            walk(c)

    walk(book)
    total_q = sum(s["question_count"] for s in flat_skills)
    assert total_q > 100


def test_chapter_guides(kb):
    guides = build_chapter_guides(kb)
    assert len(guides) >= 20
    g = guides[0]
    assert g.book_title
    assert g.chapter_title
    assert g.skills
    assert g.skill_count == len(g.skills)
    assert g.question_count >= 0
    d = g.to_dict()
    assert d["skill_count"] == len(g.skills)
    assert isinstance(d["difficulty_distribution"], dict)


def test_chapter_guides_cover_all_skills(kb):
    guides = build_chapter_guides(kb)
    total = sum(g.skill_count for g in guides)
    assert total == 3796  # 2026-09-05 并入 0.1.0 领域库(+474)
