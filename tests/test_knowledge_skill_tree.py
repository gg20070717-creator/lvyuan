# -*- coding: utf-8 -*-
"""知识技能树服务测试：从知识库派生 + 直接关联点亮（无 kw）+ 节点名精确检索。"""
import json

from brain_of_cloud.domain.models import ProgressRecord
from brain_of_cloud.knowledge.loader import KnowledgeBaseLoader
from brain_of_cloud.services.knowledge_skill_tree import KnowledgeSkillTreeService
from brain_of_cloud.storage.sqlite import SQLiteStore


def _write_kb(tmp_path):
    """写一个小知识库：入境游实战能力 / 行前 / 行程设计 / 免签240小时产品设计 / 3 技能点。"""
    master = {
        "schemaVersion": "1.0",
        "name": "入境游实战能力",
        "root": {
            "id": "ib_master", "type": "master", "title": "总库", "content": "", "parentId": None,
            "children": [{
                "id": "ib__book", "type": "book", "title": "入境游实战能力", "content": "", "parentId": "ib_master",
                "children": [{
                    "id": "ib__pre", "type": "part", "title": "行前", "content": "", "parentId": "ib__book",
                    "children": [{
                        "id": "ib__pre__design", "type": "chapter", "title": "行程设计", "content": "",
                        "parentId": "ib__pre",
                        "children": [{
                            "id": "ib__pre__design__visafree", "type": "section", "title": "免签240小时产品设计",
                            "content": "", "parentId": "ib__pre__design",
                            "children": [
                                {"id": "ib__pre__design__visafree_000", "type": "skill", "title": "行前·设计：免签240小时的政策要点",
                                 "content": "免签240小时政策要点正文……", "parentId": "ib__pre__design__visafree"},
                                {"id": "ib__pre__design__visafree_001", "type": "skill", "title": "行前·设计：停留时间计算",
                                 "content": "从入境次日零时起算……", "parentId": "ib__pre__design__visafree"},
                                {"id": "ib__pre__design__visafree_002", "type": "skill", "title": "行前·设计：经典城市线路",
                                 "content": "北京、上海、西安……", "parentId": "ib__pre__design__visafree"},
                            ],
                        }],
                    }],
                }],
            }],
        },
        "skills": [
            {"id": "ib__pre__design__visafree_000", "type": "skill", "title": "行前·设计：免签240小时的政策要点",
             "content": "免签240小时政策要点正文……", "parentId": "ib__pre__design__visafree",
             "keywords": [], "categories": ["政策"], "difficulty": 3, "status": "locked", "dependencies": []},
            {"id": "ib__pre__design__visafree_001", "type": "skill", "title": "行前·设计：停留时间计算",
             "content": "从入境次日零时起算……", "parentId": "ib__pre__design__visafree",
             "keywords": [], "categories": ["政策"], "difficulty": 3, "status": "locked", "dependencies": []},
            {"id": "ib__pre__design__visafree_002", "type": "skill", "title": "行前·设计：经典城市线路",
             "content": "北京、上海、西安……", "parentId": "ib__pre__design__visafree",
             "keywords": [], "categories": ["设计"], "difficulty": 3, "status": "locked", "dependencies": []},
        ],
    }
    p = tmp_path / "master_knowledge_base.json"
    p.write_text(json.dumps(master, ensure_ascii=False), encoding="utf-8")
    return p


class FakePlugin:
    manifest = {"plugin_id": "test_plugin"}

    def __init__(self, kb):
        self.knowledge_base = kb


def _make(tmp_path):
    _write_kb(tmp_path)
    kb = KnowledgeBaseLoader(data_dir=tmp_path).load()
    store = SQLiteStore(tmp_path / "sk.sqlite")
    store.initialize()
    svc = KnowledgeSkillTreeService(store)
    plugin = FakePlugin(kb)
    return svc, store, plugin


def _find(node_id, nodes):
    for n in nodes:
        if n["id"] == node_id:
            return n
        r = _find(node_id, n.get("children") or [])
        if r:
            return r
    return None


class TestKnowledgeSkillTree:
    def test_derive_structure(self, tmp_path):
        """派生树 = 知识库结构直接投影（book → part → chapter → section → skill）。"""
        svc, _, plugin = _make(tmp_path)
        branches = svc.derive(plugin.knowledge_base)
        assert len(branches) == 1
        b = branches[0]
        assert b["id"] == "ib__book" and b["name"] == "入境游实战能力" and b["type"] == "book"
        part = b["children"][0]
        assert part["type"] == "part" and part["name"] == "行前"
        ch = part["children"][0]
        assert ch["type"] == "chapter" and ch["name"] == "行程设计"
        sec = ch["children"][0]
        assert sec["type"] == "section" and sec["name"] == "免签240小时产品设计"
        assert [c["type"] for c in sec["children"]] == ["skill", "skill", "skill"]

    def test_mastery_lit_direct_link(self, tmp_path):
        """新口径：主客观综合掌握度（此处用 baseline 画像评估代表）；父节点=子树平均；100=完全点亮。"""
        svc, store, plugin = _make(tmp_path)
        store.save_mastery_assessment("u1", "ib__pre__design__visafree_000", "baseline", 100)
        store.save_mastery_assessment("u1", "ib__pre__design__visafree_001", "baseline", 100)
        tree = svc.get_tree("u1", plugin)
        sec = _find("ib__pre__design__visafree", tree["branches"])
        assert sec["linked_count"] == 3
        # (100+100+0)/3 ≈ 66.7 → 未完全点亮，但 fill 有值
        assert sec["mastery"] == 67
        assert sec["lit"] is False and sec["fill"] is not None
        ch = _find("ib__pre__design", tree["branches"])
        assert ch["mastery"] == 67
        sk2 = _find("ib__pre__design__visafree_002", tree["branches"])
        assert sk2["mastery"] == 0 and sk2["fill"] == 0.0 and sk2["lit"] is False
        # 全满 → 100% 完全点亮（auto）
        store.save_mastery_assessment("u1", "ib__pre__design__visafree_002", "baseline", 100)
        tree2 = svc.get_tree("u1", plugin)
        sec2 = _find("ib__pre__design__visafree", tree2["branches"])
        assert sec2["mastery"] == 100 and sec2["lit"] is True and sec2["source"] == "auto"

    def test_concierge_activation(self, tmp_path):
        """管家确认点亮（concierge）优先于自动。"""
        svc, store, plugin = _make(tmp_path)
        store.save_skill_activation("a1", "u1", "ib__pre__design__visafree", reason="管家确认", source="concierge")
        tree = svc.get_tree("u1", plugin)
        sec = _find("ib__pre__design__visafree", tree["branches"])
        assert sec["lit"] is True and sec["source"] == "concierge" and sec["reason"] == "管家确认"

    def test_structural_search_exact_and_contains(self, tmp_path):
        """按节点显示名检索：精确标题命中优先，返回子树技能点。"""
        svc, _, plugin = _make(tmp_path)
        kb = plugin.knowledge_base
        r = svc.structural_search("免签240小时产品设计", kb)
        assert r["exact"] is True and r["count"] == 1
        m = r["results"][0]
        assert m["type"] == "section" and m["path"][-1] == "免签240小时产品设计"
        assert len(m["skills"]) == 3
        # 包含命中兜底
        r2 = svc.structural_search("免签240", kb)
        assert r2["count"] >= 1 and r2["exact"] is False
        # 无命中
        r3 = svc.structural_search("不存在的节点", kb)
        assert r3["count"] == 0

    def test_counts(self, tmp_path):
        """get_tree 返回节点计数。"""
        svc, _, plugin = _make(tmp_path)
        tree = svc.get_tree("u1", plugin)
        assert tree["counts"]["books"] == 1
        assert tree["counts"]["parts"] == 1
        assert tree["counts"]["chapters"] == 1
        assert tree["counts"]["sections"] == 1
        assert tree["counts"]["skills"] == 3
