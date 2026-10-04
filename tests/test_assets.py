"""Asset（文件资产）存储层测试 — 覆盖 assets 表 CRUD。"""

from __future__ import annotations

from brain_of_cloud.domain.models import Asset, AssetType
from brain_of_cloud.storage.sqlite import SQLiteStore
from brain_of_cloud.services.assets import AssetService


def _store(tmp_path):
    store = SQLiteStore(tmp_path / "test_assets.sqlite")
    store.initialize()
    return store


def _asset(**overrides) -> Asset:
    base = dict(
        asset_id="asset_001",
        user_id="u1",
        session_id="s1",
        title="突发事件处理讲义",
        asset_type=AssetType.LECTURE,
        content="突发事件应急处置流程…",
        source_tool="generate_material",
        created_at="2026-08-18T10:00:00+00:00",
    )
    base.update(overrides)
    return Asset(**base)


def test_asset_model_defaults():
    a = _asset()
    assert a.asset_id == "asset_001"
    assert a.asset_type == AssetType.LECTURE
    assert a.source_tool == "generate_material"


def test_save_and_list_assets(tmp_path):
    store = _store(tmp_path)
    store.save_asset(_asset())
    rows = store.get_assets("u1")
    assert len(rows) == 1
    assert rows[0]["title"] == "突发事件处理讲义"
    assert rows[0]["asset_type"] == "lecture"


def test_asset_type_filter(tmp_path):
    store = _store(tmp_path)
    store.save_asset(_asset(asset_id="a1", asset_type=AssetType.LECTURE))
    store.save_asset(_asset(asset_id="a2", asset_type=AssetType.PLAN))
    store.save_asset(_asset(asset_id="a3", asset_type=AssetType.PLAN))
    plans = store.get_assets("u1", asset_type=AssetType.PLAN)
    assert len(plans) == 2
    lectures = store.get_assets("u1", asset_type=AssetType.LECTURE)
    assert len(lectures) == 1


def test_user_isolation(tmp_path):
    store = _store(tmp_path)
    store.save_asset(_asset(asset_id="a1", user_id="u1"))
    store.save_asset(_asset(asset_id="a2", user_id="u2"))
    assert len(store.get_assets("u1")) == 1


def test_get_and_delete_asset(tmp_path):
    store = _store(tmp_path)
    store.save_asset(_asset())
    got = store.get_asset("asset_001")
    assert got is not None and got["content"].startswith("突发事件")
    assert store.get_asset("asset_missing") is None
    assert store.delete_asset("asset_001") is True
    assert store.get_asset("asset_001") is None
    assert store.delete_asset("asset_001") is False


def test_asset_service_create_and_list(tmp_path):
    store = _store(tmp_path)
    svc = AssetService(store)
    created = svc.create(
        user_id="u1", session_id="s1",
        title="个性化备考计划", asset_type=AssetType.PLAN,
        content="第1周：法规…", source_tool="generate_plan",
    )
    assert created["asset_id"].startswith("asset_")
    assert created["title"] == "个性化备考计划"
    rows = svc.list("u1")
    assert len(rows) == 1
    assert rows[0]["asset_type"] == "plan"
    detail = svc.get(created["asset_id"])
    assert detail is not None and detail["content"] == "第1周：法规…"
    assert svc.delete(created["asset_id"]) is True


def test_sync_wrong_book_per_question_cards(tmp_path):
    """易错题·降维解释 = 每道错题一张卡片，内容含对话中的降维解释。"""
    store = _store(tmp_path)
    store.save_wrong_answer(
        user_id="u1", question_id="q1", knowledge_point_id="kp1", skill_title="技能点A",
        prompt="题目一?", options=["A. 甲", "B. 乙"], user_answer="A", correct_answer="B",
        explanation="标准解析", difficulty="basic", source="bank",
    )
    store.update_wrong_reteach_note("u1", "q1", "大白话：为什么错、怎么记")
    store.save_wrong_answer(
        user_id="u1", question_id="q2", knowledge_point_id="kp1", skill_title="技能点A",
        prompt="题目二?", options=["A. 对", "B. 错"], user_answer="A", correct_answer="B",
        explanation="标准解析二", difficulty="advanced", source="bank",
    )
    store.update_wrong_reteach_note("u1", "q2", "换个角度：步骤顺序记")
    svc = AssetService(store)
    svc.sync_wrong_book("u1", store.list_wrong_answers("u1"))
    cards = svc.list("u1", asset_type="wrong_book")
    # 每道错题一张独立卡片（不是把所有题塞进一个文件）
    assert len(cards) == 2
    contents = {c["content"] for c in cards}
    assert any("## 题目一?" in c and "## 降维解释" in c and "大白话：为什么错、怎么记" in c for c in contents)
    assert any("## 题目二?" in c and "## 降维解释" in c and "换个角度：步骤顺序记" in c for c in contents)
