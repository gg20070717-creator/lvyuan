# -*- coding: utf-8 -*-
"""把 L5 技能点名写入跨文化知识库骨架（content 留空，供后续 API 填充）。

用法:  python scripts/name_cross_culture_skills.py
输入:  data/culture_customs_kb.json, data/cultural_bridge_kb.json（骨架）
输出:  同上（每个 section 下挂 3 个 skill，并写入顶层 skills 平铺数组）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cross_culture_skill_data import SKILL_NAMES  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CUSTOMS_FILE = DATA_DIR / "culture_customs_kb.json"
BRIDGE_FILE = DATA_DIR / "cultural_bridge_kb.json"

COUNTRY_CODES = list(SKILL_NAMES.keys())


def code_from_part_id(part_id: str) -> str:
    # cc__us / cc__us__bridge -> us
    return part_id.split("__")[1]


def make_skill(section: dict, idx: int, title: str, category: str) -> dict:
    return {
        "id": f"{section['id']}_{idx:03d}",
        "type": "skill",
        "title": title,
        "content": "",
        "parentId": section["id"],
        "keywords": [],
        "categories": [category],
        "difficulty": 3,
        "status": "locked",
        "dependencies": [],
    }


def find_sections(book: dict) -> list[dict]:
    """返回 (part_id, chapter, section) 列表。"""
    out = []
    for part in book.get("children") or []:
        for ch in part.get("children") or []:
            for sec in ch.get("children") or []:
                out.append((part, ch, sec))
    return out


def fill_kb(path: Path, dims_map: dict, book_title: str) -> int:
    kb = json.loads(path.read_text(encoding="utf-8"))
    book = kb["root"]["children"][0]
    skills_flat = []
    total = 0
    missing = []

    for part, ch, sec in find_sections(book):
        code = code_from_part_id(part["id"])
        dim_key = ch["id"].split("__")[-1]
        topic_key = sec["id"].split("__")[-1]
        # 查数据：customs 用 SKILL_NAMES[code][dim_key][topic_key]；
        # bridge 用 SKILL_NAMES[code]["bridge"][dim_key][topic_key]
        entry = SKILL_NAMES.get(code, {})
        if book_title == "文化桥":
            entry = entry.get("bridge", {})
        titles = entry.get(dim_key, {}).get(topic_key)

        # 幂等：清掉该 section 下已有 skill
        sec["children"] = [c for c in sec.get("children") or [] if c["type"] != "skill"]
        sec["childIds"] = [c["id"] for c in sec.get("children") or []]

        if titles is None:
            missing.append(f"{part['title']}/{ch['title']}/{sec['title']} (dim={dim_key}, topic={topic_key})")
            continue

        for i, title in enumerate(titles):
            sk = make_skill(sec, i, title, ch["title"])
            sec.setdefault("children", []).append(sk)
            sec["childIds"].append(sk["id"])
            skills_flat.append(sk)
            total += 1

    if missing:
        raise SystemExit(f"[{path.name}] 缺少技能点数据: {len(missing)}\n" + "\n".join(missing[:20]))

    # 顶层 skills 平铺数组
    kb["skills"] = skills_flat

    # 重算 stats（master + book）
    def add_stats(node):
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

    for node in (kb["root"], book):
        node["stats"] = {"title": node["title"], **add_stats(node)}

    path.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {path.name}: 写入 {total} 个技能点")
    return total


def validate(path: Path) -> None:
    kb = json.loads(path.read_text(encoding="utf-8"))
    ids = set()
    tree_skills = 0
    problems = []

    def walk(node):
        nonlocal tree_skills
        nid = node["id"]
        if nid in ids:
            problems.append(f"重复 ID: {nid}")
        ids.add(nid)
        if node["type"] == "skill":
            tree_skills += 1
        for c in node.get("children") or []:
            if c.get("parentId") != nid:
                problems.append(f"parentId 错误: {c['id']} -> {c.get('parentId')} (应为 {nid})")
            walk(c)

    walk(kb["root"])
    flat = kb["skills"]
    if len(flat) != tree_skills:
        problems.append(f"skills 平铺({len(flat)})与树({tree_skills})不一致")
    for s in flat:
        if s["parentId"] not in ids:
            problems.append(f"skill parentId 不存在: {s['id']}")
        if not s["title"]:
            problems.append(f"skill 无标题: {s['id']}")
    if problems:
        raise SystemExit(f"[{path.name}] 校验失败:\n" + "\n".join(problems[:30]))
    print(f"  ✓ {path.name} 校验通过: 技能点 {len(flat)}，节点总数 {len(ids)}")


def main() -> None:
    total = 0
    for path, book_title in [(CUSTOMS_FILE, "文化习惯知识"), (BRIDGE_FILE, "文化桥")]:
        print(f"== {book_title} ==")
        total += fill_kb(path, None, book_title)
        validate(path)
    print(f"\n共新增技能点: {total}")


if __name__ == "__main__":
    main()