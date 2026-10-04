# -*- coding: utf-8 -*-
"""知识技能树服务 — 从知识库结构直接派生技能树，替代抽象 kw 关键词映射。

设计（解决 kw「假大空」）：
1. 派生：book → (part) → chapter → section → skill，节点 id 复用知识库节点 id（精确定位）；
2. 点亮：节点直接关联自己的子树技能点（不靠关键词），mastery = 子树技能点平均掌握度，
   ≥0.7 自动点亮（source=auto）；管家确认仍可 concierge 点亮；
3. 检索：structural_search(query) 按「节点显示名」精确/包含命中 → 直接返回该节点子树技能点。
"""
from __future__ import annotations

from typing import Any
from brain_of_cloud.services.mastery import MasteryService

_BOOK_ICONS = {
    "全国导游基础知识": "book",
    "导游业务": "briefcase",
    "政策与法律法规": "scale",
    "地方导游基础知识": "map",
    "文化习惯知识": "globe",
    "文化桥": "bridge",
    "入境游实战能力": "target",
}
_TYPE_ICONS = {"part": "folder", "chapter": "file", "section": "list", "skill": "dot"}


def _norm(s: str) -> str:
    return s.replace(" ", "").lower()


class KnowledgeSkillTreeService:
    """从知识库派生技能树；点亮/掌握度按节点直接关联技能点；支持节点名精确检索。"""

    def __init__(self, store: Any) -> None:
        self._store = store

    # ---------- 派生树 ----------

    def derive(self, kb: Any) -> list[dict[str, Any]]:
        """把知识库结构递归投影为嵌套技能树（book -> part? -> chapter -> section -> skill）。"""
        return [
            self._build_node(book, icon=_BOOK_ICONS.get(book["title"], "book"))
            for book in kb.books
        ]

    def _build_node(self, node: dict, icon: str | None = None) -> dict[str, Any]:
        t = node["type"]
        n = {
            "id": node["id"],
            "type": t,
            "name": node["title"],
            "ic": icon or _TYPE_ICONS.get(t, "sparkle"),
            "lit": False,
            "source": "",
            "reason": "",
            "mastery": None,
            "linked_count": 0,
            "children": [self._build_node(c) for c in node.get("children") or []],
        }
        return n

    # ---------- 点亮 / 掌握度 ----------

    def get_tree(self, user_id: str, plugin: Any | None = None) -> dict[str, Any]:
        kb = getattr(plugin, "knowledge_base", None)
        if kb is None:
            return {"user_id": user_id, "branches": [], "counts": {}}
        branches = self.derive(kb)
        # 从派生树上收集全部技能点 id（不依赖 plugin._kb 等私有结构）
        all_kps: list[str] = []
        def _collect_skills(node: dict) -> None:
            if node.get("type") == "skill":
                all_kps.append(node["id"])
                return
            for ch in node.get("children") or []:
                _collect_skills(ch)
        for _b in branches:
            _collect_skills(_b)
        # 主客观综合掌握度（客观=题库通过率；主观=管家/沙盒/画像评估，沙盒为预留接口）
        mastery_by_skill: dict[str, float] = {}
        details: dict[str, dict[str, object]] = {}
        if plugin is not None and all_kps:
            try:
                ms = MasteryService(plugin, self._store)
            except Exception:
                ms = None
            for kp in all_kps:
                try:
                    d = ms.skill_mastery(user_id, kp)
                except Exception:
                    continue
                mastery_by_skill[kp] = float(d["mastery"]) / 100.0
                details[kp] = d
        activations = self._load_activations(user_id)
        for branch in branches:
            self._annotate(branch, mastery_by_skill, activations, details)
        return {
            "user_id": user_id,
            "branches": branches,
            "counts": self._counts(branches),
        }

    def _counts(self, branches: list[dict[str, Any]]) -> dict[str, int]:
        c = {"books": len(branches), "parts": 0, "chapters": 0, "sections": 0, "skills": 0}
        key = {"part": "parts", "chapter": "chapters", "section": "sections", "skill": "skills"}

        def walk(node: dict) -> None:
            k = key.get(node["type"])
            if k:
                c[k] += 1
            for ch in node.get("children") or []:
                walk(ch)

        for b in branches:
            walk(b)
        return c

    def _load_activations(self, user_id: str) -> dict[str, str]:
        act: dict[str, str] = {}
        try:
            rows = self._store.list_skill_activations(user_id)
        except Exception:
            return act
        for r in rows:
            if r.get("source") == "concierge" and r.get("node_id"):
                act[r["node_id"]] = r.get("reason") or "司南确认你已掌握"
        return act

    def _annotate(
        self,
        node: dict,
        mastery_by_skill: dict[str, float],
        activations: dict[str, str],
        details: dict[str, dict[str, object]] | None = None,
    ) -> None:
        """递归给节点打综合掌握度/填充比例/点亮（100%=完全点亮）。

        叶子=技能点主客观综合分；父节点=子树平均。
        """
        if node["type"] == "skill":
            node["mastery"] = 0
            node["fill"] = 0.0
            m = mastery_by_skill.get(node["id"])
            if m is not None:
                node["mastery"] = round(m * 100)
                node["fill"] = round(m, 3)
                node["mastery_detail"] = (details or {}).get(node["id"])
            node["linked_count"] = 1
            if node["id"] in activations:
                node["lit"], node["source"], node["reason"] = True, "concierge", activations[node["id"]]
            elif (node.get("mastery") or 0) >= 100:
                node["lit"], node["source"] = True, "auto"
                node["reason"] = "综合掌握度 100%（完全点亮）"
            return
        vals: list[float] = []
        linked = 0
        for c in node.get("children") or []:
            self._annotate(c, mastery_by_skill, activations, details)
            if c.get("mastery") is not None:
                vals.append(c["mastery"] / 100.0)
            linked += c.get("linked_count", 0)
        node["linked_count"] = linked
        node["mastery"] = 0
        node["fill"] = 0.0
        if vals:
            node["mastery"] = round(sum(vals) / len(vals) * 100)
            node["fill"] = round(sum(vals) / len(vals), 3)
        if node["id"] in activations:
            node["lit"], node["source"], node["reason"] = True, "concierge", activations[node["id"]]
        elif vals and sum(vals) / len(vals) >= 1.0:
            node["lit"], node["source"] = True, "auto"
            node["reason"] = f"关联 {linked} 个技能点，平均掌握度 100%（完全点亮）"


    def structural_search(self, query: str, kb: Any) -> dict[str, Any]:
        """按节点显示名检索知识库：精确标题优先，其次包含；返回命中的节点子树技能点。"""
        index: dict[str, list[dict[str, Any]]] = {}

        def walk(node: dict, path: list[str]) -> None:
            skills: list[dict[str, Any]] = []

            def collect(n: dict) -> None:
                for c in n.get("children") or []:
                    if c["type"] == "skill":
                        skills.append(c)
                    else:
                        collect(c)

            collect(node)
            index.setdefault(_norm(node["title"]), []).append({
                "id": node["id"], "type": node["type"], "name": node["title"],
                "path": path + [node["title"]], "skills": skills,
            })
            for c in node.get("children") or []:
                if c["type"] != "skill":
                    walk(c, path + [node["title"]])

        for book in kb.books:
            walk(book, ["总库"])

        q = _norm(query)
        exact = index.get(q, [])
        contains = [info for key, lst in index.items() if q in key for info in lst]
        matches = exact or contains
        results = []
        for m in matches:
            results.append({
                "id": m["id"], "type": m["type"], "name": m["name"],
                "path": m["path"],
                "skills": [
                    {"id": s["id"], "title": s["title"], "difficulty": s.get("difficulty", 3),
                     "status": s.get("status", "locked"),
                     "content_excerpt": (s.get("content") or "")[:100]}
                    for s in m["skills"][:50]
                ],
            })
        return {"query": query, "exact": bool(exact), "count": len(results), "results": results}

