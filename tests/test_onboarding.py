# -*- coding: utf-8 -*-
"""初试引导核心（M1）：67 组索引 / 画像 / baseline / 路径解析校验展开。"""
import pytest

from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.mastery import MasteryService
from brain_of_cloud.services.onboarding import (
    IDENTITY_QUESTIONS,
    STATUS_LEARNING,
    STATUS_MASTERED,
    apply_baseline,
    build_group_index,
    build_persona,
    build_route_record,
    sync_learner_profile,
    default_group_status,
    expand_plan,
    parse_group_order,
    validate_group_order,
)
from brain_of_cloud.storage.sqlite import SQLiteStore


@pytest.fixture(scope="module")
def plugin():
    return TourGuidePlugin()


@pytest.fixture()
def store(tmp_path):
    s = SQLiteStore(tmp_path / "onb.sqlite")
    s.initialize()
    return s


def test_identity_questions_count():
    assert len(IDENTITY_QUESTIONS) == 6
    for q in IDENTITY_QUESTIONS:
        assert q["id"] and len(q["options"]) >= 4


def test_group_index_shape(plugin):
    idx = build_group_index(plugin)
    domains = idx["domains"]
    groups = idx["groups"]
    order = idx["order"]
    assert len(domains) == len(plugin._kb.books)  # 动态：随并入书变化
    assert len(groups) == 84  # 2026-09-05 收纳到 7 大领域后组数
    assert len(order) == len(groups)
    total = sum(len(gi.skill_ids) for gi in groups.values())
    assert total == 3796
    # 全部组都挂在某 book 下
    books = {b["id"] for b in plugin._kb.books}  # noqa: SLF001
    assert {gi.book_id for gi in groups.values()} <= books


def test_persona_and_defaults(plugin):
    answers = {"identity": "guide", "basis": "guide_return", "language": "basic",
               "goal": "inbound_foreign", "pace": "parttime", "style": "practice"}
    persona = build_persona(answers)
    assert persona["persona_id"] == "guide_inbound"
    assert "导游业务" in persona["default_master_books"]
    idx = build_group_index(plugin)
    gs = default_group_status(persona, idx["groups"])
    mastered = [gid for gid, v in gs.items() if v == STATUS_MASTERED]
    # 动态：导游业务域内全部默认掌握组（原 3 章 + 并入的真实岗位实务 5 组）
    assert len(mastered) == sum(1 for g in idx["groups"].values() if g.book_title == "导游业务")
    assert all(idx["groups"][gid].book_title == "导游业务" for gid in mastered)


def test_apply_baseline_and_mastery(plugin, store):
    idx = build_group_index(plugin)
    group = next(gi for gi in idx["groups"].values() if gi.book_title == "导游业务")
    others = [g for g in idx["order"] if g != group.id]
    status = {gid: STATUS_LEARNING for gid in idx["order"]}
    status[group.id] = STATUS_MASTERED
    res = apply_baseline(store, "u1", status, idx["groups"])
    assert res["mastered_group_count"] == 1
    assert res["mastered_skills"] == group.skill_count
    rows = store.get_mastery_assessments("u1")
    assert len(rows) == group.skill_count
    ms = MasteryService(plugin, store)
    assert ms.skill_mastery("u1", group.skill_ids[0])["mastery"] == 100.0
    # 全部 learning → baseline 清空
    status2 = {gid: STATUS_LEARNING for gid in idx["order"]}
    apply_baseline(store, "u1", status2, idx["groups"])
    assert store.get_mastery_assessments("u1") == []


def test_parse_validate_expand(plugin):
    idx = build_group_index(plugin)
    canonical = list(idx["order"])
    # JSON 数组（乱序也算排全）
    rev = list(reversed(canonical))
    ids, errs = parse_group_order(__import__("json").dumps(rev), idx["groups"])
    assert not errs
    v = validate_group_order(ids, idx["groups"])
    assert v["ok"] and v["count"] == len(canonical) and v["missing"] == []
    # 缺一个
    ids2, _ = parse_group_order(__import__("json").dumps(canonical[:-1]), idx["groups"])
    v2 = validate_group_order(ids2, idx["groups"])
    assert not v2["ok"] and v2["missing"] == [canonical[-1]]
    # 未知 ID
    v3 = validate_group_order(canonical[:-1] + ["__fake__"], idx["groups"])
    assert not v3["ok"] and "__fake__" in v3["unknown"]
    # 行式解析（序号+ID+标题）
    g0 = idx["groups"][canonical[0]]
    lines = f"1. {g0.id} {g0.title}\n" + "\n".join(f"{i+2}. {g}" for i, g in enumerate(canonical[1:]))
    ids3, errs3 = parse_group_order(lines, idx["groups"])
    assert not errs3 and ids3 == canonical
    # expand：把第 1 组设 mastered
    mastered = {canonical[0]}
    exp = expand_plan(canonical, idx["groups"], mastered)
    first_skills = set(idx["groups"][canonical[0]].skill_ids)
    assert set(exp["before_start"]) == first_skills
    all_skills = set().union(*[set(idx["groups"][g].skill_ids) for g in canonical])
    assert set(exp["path"]) == (all_skills - first_skills)
    assert exp["total"] == 3796
    assert not (set(exp["before_start"]) & set(exp["path"]))


def test_sync_learner_profile(store):
    answers = {"identity": "guide", "basis": "guide_return", "language": "fluent",
               "goal": "custom_high", "pace": "parttime", "style": "practice"}
    persona = build_persona(answers)
    sync_learner_profile(store, "u_sync", persona, answers)
    lp = store.get_learner_profile("u_sync")
    assert lp is not None
    assert persona["label"] in lp.current_level
    assert lp.target_role == "定制旅行 / 高端入境定制"
    assert lp.style_preferences.get("mode") == "场景演练"
    assert lp.baseline_scores == {}


def test_build_route_record(plugin):
    idx = build_group_index(plugin)
    rec = build_route_record("u1", list(idx["order"]), idx["groups"], mastered_group_ids=set())
    assert rec["stats"]["groups"] == len(idx["order"])
    assert rec["stats"]["total_skills"] == 3796
    assert len(rec["group_order"]) == len(idx["order"])
