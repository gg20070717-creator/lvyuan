"""结构化引用链（T14 / IR-1、D-11）：资产 ↔ 知识片段 chunk_id 溯源。"""
import json
from unittest.mock import MagicMock

from brain_of_cloud.domain.models import Asset, AssetType
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.assets import AssetService
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def test_asset_service_persists_evidence_ids(tmp_path):
    store = SQLiteStore(tmp_path / "a.sqlite")
    store.initialize()
    svc = AssetService(store)

    asset = svc.create(
        "u1", "园林构景讲义", "内容……",
        asset_type=AssetType.LECTURE,
        evidence_ids=["b01__skill_00098", "b01__skill_00102"],
    )

    assert asset["evidence_ids"] == ["b01__skill_00098", "b01__skill_00102"]
    loaded = store.get_asset(asset["asset_id"])
    assert loaded["evidence_ids"] == ["b01__skill_00098", "b01__skill_00102"]
    listed = store.get_assets("u1")
    assert listed[0]["evidence_ids"] == ["b01__skill_00098", "b01__skill_00102"]


def test_legacy_db_migration_adds_column(tmp_path):
    """老库（无 evidence_ids_json 列）初始化后自动迁移。"""
    import sqlite3
    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE assets (asset_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
        "session_id TEXT NOT NULL DEFAULT '', title TEXT NOT NULL, asset_type TEXT NOT NULL, "
        "content TEXT NOT NULL, source_tool TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO assets VALUES ('a1','u1','','旧讲义','lecture','旧内容','generate_material','2026-01-01')"
    )
    conn.commit()
    conn.close()

    store = SQLiteStore(db)
    store.initialize()

    loaded = store.get_asset("a1")
    assert loaded["evidence_ids"] == []  # 旧资产默认空引用链


def test_generate_material_records_evidence_ids(tmp_path):
    """generate_material 生成的材料资产记录证据 chunk_id（端到端）。"""
    store = SQLiteStore(tmp_path / "b.sqlite")
    store.initialize()
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=llm)
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")

    evidence_json = json.dumps({
        "results": [
            {"chunk_id": "kp_welcome", "content": "欢迎词要点……", "source": "inbound-guide/welcome"},
            {"chunk_id": "kp_cross_culture", "content": "跨文化要点……", "source": "inbound-guide/culture"},
        ]
    })
    orch._text_generator.run = MagicMock(return_value="生成的讲义内容")

    payload = json.loads(orch._handle_generate_material("生成欢迎词讲义", evidence_json))

    asset = store.get_asset(payload["asset_id"])
    assert set(asset["evidence_ids"]) == {"kp_welcome", "kp_cross_culture"}
