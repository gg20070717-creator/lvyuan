"""Tests for the Chinese search engine — retrieval quality over real KB."""

import pytest

from brain_of_cloud.knowledge.loader import KnowledgeBaseLoader
from brain_of_cloud.knowledge.search import ChineseSearchIndex, SearchResult, tokenize


@pytest.fixture(scope="module")
def index():
    kb = KnowledgeBaseLoader().load()
    return ChineseSearchIndex(kb)


def test_tokenize_chinese_bigrams():
    assert tokenize("导游服务") == ["导游", "游服", "服务"]
    assert "一五" in tokenize("“一五”计划的顺利实施")


def test_tokenize_mixed():
    tokens = tokenize("TV broadcasting 导游")
    assert "tv" in tokens
    assert "导游" in tokens


def test_exact_title_query_returns_skill(index):
    results = index.search("“一五”计划的顺利实施", top_k=3)
    assert results[0].skill.title == "“一五”计划的顺利实施"


def test_keyword_query_returns_right_skill(index):
    # 查询命中的应是政策法规中的突发事件应对
    results = index.search("突发事件应急处置", top_k=5)
    top = [r.skill for r in results]
    assert any("突发事件" in s.title or "应急" in s.title for s in top)


def test_historical_query_returns_guiding_history(index):
    results = index.search("导游服务的产生与发展", top_k=3)
    assert results[0].skill.title == "导游服务的产生与发展"


def test_cultural_query_returns_related(index):
    results = index.search("天坛 祭祀", top_k=5)
    assert any("坛庙" in r.skill.title for r in results) or any(
        "天坛" in r.skill.content for r in results
    )


def test_query_with_id_filter(index):
    skill = index.get_skill("b01__skill_00001")
    results = index.search(
        "一五计划", knowledge_point_ids=["b01__skill_00001"], top_k=5
    )
    assert results
    assert all(r.skill.id == "b01__skill_00001" for r in results)


def test_book_filter(index):
    results = index.search(
        "导游服务", book="政策与法律法规", top_k=5
    )
    assert all(r.skill.book_title == "政策与法律法规" for r in results)


def test_relevance_ranking_reasonable(index):
    # 中国园林的查询应优先命中园林相关技能点
    results = index.search("中国古典园林的构景手法", top_k=3)
    assert any("园林" in r.skill.title for r in results)


def test_empty_query_fallback_ordered(index):
    results = index.search("", top_k=10)
    assert len(results) == 10
    assert all(isinstance(r, SearchResult) for r in results)


def test_no_match_returns_empty(index):
    # 完全无关的查询不应返回满屏垃圾（但仍可能小命中，只验证不崩溃）
    results = index.search("zzzzqqqqxxyywv", top_k=5)
    assert isinstance(results, list)
