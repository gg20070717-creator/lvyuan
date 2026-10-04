# -*- coding: utf-8 -*-
"""把两个跨文化知识库合并进 data/master_knowledge_base.json，与教材库一起读取。

合并方式：
- 文化习惯知识、文化桥 作为两个 book 节点挂到主库 master 下（master → book → part → chapter → section → skill）；
- 顶层 skills[] 平铺数组按树重建（713 教材 + 1080 文化习惯 + 1440 文化桥 = 3233）；
- 幂等：重复运行不会产生重复 book / 重复 skill。

用法: python scripts/merge_cross_culture_kb.py
输出: data/master_knowledge_base.json（合并后）
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MASTER = DATA / "master_knowledge_base.json"
SOURCES = {
    "文化习惯知识": DATA / "culture_customs_kb.json",
    "文化桥": DATA / "cultural_bridge_kb.json",
    "入境游实战能力": DATA / "inbound_practice_kb.json",
}
BOOK_IDS = {"cc_book_customs", "cc_book_bridge", "ib__book"}


def add_stats(node: dict) -> dict:
    c = {"parts": 0, "chapters": 0, "sections": 0, "skills": 0}
    for child in node.get("children") or []:
        t = child["type"]
        if t == "part":
            c["parts"] += 1
        elif t == "chapter":
            c["chapters"] += 1
        elif t == "section":
            c["sections"] += 1
        elif t == "skill":
            c["skills"] += 1
        sub = add_stats(child)
        for k in c:
            c[k] += sub[k]
    return c


def rebuild_flat(kb: dict) -> None:
    flat = []

    def walk(node: dict) -> None:
        if node["type"] == "skill":
            flat.append(node)
            return
        for c in node.get("children") or []:
            walk(c)

    walk(kb["root"])
    kb["skills"] = flat


def main() -> None:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    root = master["root"]
    master_id = root["id"]

    # 幂等：先移除已合并过的跨文化 book
    before = len(root.get("children") or [])
    root["children"] = [b for b in root.get("children") or [] if b.get("id") not in BOOK_IDS]
    root["childIds"] = [b["id"] for b in root["children"]]
    removed = before - len(root["children"])
    if removed:
        print(f"清理已合并的跨文化 book: {removed} 个（幂等）")

    # 追加两个跨文化 book
    for title, path in SOURCES.items():
        src = json.loads(path.read_text(encoding="utf-8"))
        book = src["root"]["children"][0]
        if book["title"] != title:
            raise SystemExit(f"{path.name} 的 book 标题不是 {title}，请检查")
        book["parentId"] = master_id
        book.pop("sourceFile", None)
        # 重算该 book 的 stats
        book["stats"] = {"title": title, **add_stats(book)}
        root.setdefault("children", []).append(book)
        root["childIds"] = [b["id"] for b in root["children"]]
        print(f"已合并: {title}（skills={len(src['skills'])}）")

    # 顶层 skills 平铺按树重建
    rebuild_flat(master)
    root["stats"] = {"title": root["title"], **add_stats(root)}
    master["skills"] = master["skills"]

    MASTER.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n合并完成 -> {MASTER}")
    print(f"books = {len(root['children'])} | skills = {len(master['skills'])} | 顶层 stats = {root['stats']}")


if __name__ == "__main__":
    main()