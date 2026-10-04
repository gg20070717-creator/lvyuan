#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 0.1.0 并入的 17 本从顶层并列降为「7 大领域」下的 part，减少前端顶层拥挤。

规则：
  gp_* (真实岗位实务 5 本)        -> 导游业务
  cu_* (旅游定制师 6 本)          -> 入境游实战能力
  inb_* 含「跨文化」                -> 文化习惯知识
  inb_* 含「讲解/翻译」             -> 入境游实战能力
  inb_* 其它（客源国 4 本）         -> 文化习惯知识
用法：
  python scripts/nest_b_kb_books_into_domains.py --dry-run
  python scripts/nest_b_kb_books_into_domains.py
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "data", "master_knowledge_base.json")
NEW_PREFIXES = ("gp_", "cu_", "inb_")


def walk(node):
    yield node
    for c in node.get("children") or []:
        yield from walk(c)


def fix_stats(node):
    from collections import Counter
    cnt = Counter()
    for n in walk(node):
        if n.get("type"):
            cnt[n["type"]] += 1
    node["stats"] = {
        "title": node.get("title", ""),
        "parts": cnt.get("part", 0),
        "chapters": cnt.get("chapter", 0),
        "sections": cnt.get("section", 0),
        "skills": cnt.get("skill", 0),
    }


def pick_host(hosts, node):
    title = node.get("title", "")
    nid = node.get("id", "")
    if nid.startswith("gp_"):
        return hosts.get("导游业务")
    if nid.startswith("cu_"):
        return hosts.get("入境游实战能力")
    if nid.startswith("inb_"):
        if "跨文化" in title:
            return hosts.get("文化习惯知识")
        if ("讲解" in title) or ("翻译" in title):
            return hosts.get("入境游实战能力")
        return hosts.get("文化习惯知识")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", default=MASTER)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.master, encoding="utf-8") as f:
        master = json.load(f)
    root = master["root"]
    books = [c for c in root.get("children", []) if c.get("type") == "book"]
    hosts = {b["title"]: b for b in books if not b.get("id", "").startswith(NEW_PREFIXES)}
    missing = [t for t in ("导游业务", "入境游实战能力", "文化习惯知识") if t not in hosts]
    if missing:
        raise SystemExit("缺少宿主领域: %s" % missing)

    news = [b for b in books if b.get("id", "").startswith(NEW_PREFIXES)]
    print("hosts:", {t: b["id"] for t, b in hosts.items()})
    print("new top books to nest:", len(news))

    plan = []
    for nb in news:
        host = pick_host(hosts, nb)
        plan.append((nb["id"], nb.get("title"), host["id"], host["title"] if host else None))
        if host is None:
            raise SystemExit("无法归类: %s %s" % (nb.get("id"), nb.get("title")))
    for row in plan:
        print("  %-12s %-24s -> %s(%s)" % (row[0], row[1][:20], row[3], row[2]))

    if args.dry_run:
        return

    # 备份
    bak = os.path.join(tempfile.gettempdir(), "master_knowledge_base.pre-nest.json")
    shutil.copy2(args.master, bak)
    print("备份:", bak)

    moved = 0
    root["children"] = [c for c in root["children"] if not c.get("id", "").startswith(NEW_PREFIXES)]
    for nb in news:
        host = pick_host(hosts, nb)
        nb["type"] = "part"
        nb["parentId"] = host["id"]
        fix_stats(nb)
        host.setdefault("children", []).append(nb)
        host["childIds"] = [c.get("id") for c in host["children"]]
        fix_stats(host)
        moved += 1
    root["childIds"] = [c.get("id") for c in root["children"]]
    fix_stats(root)

    tmp = args.master + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False)
    os.replace(tmp, args.master)
    print("完成：顶层 books=%d，共迁移 %d 本为 part（技能点不变）" % (
        len(root["children"]), moved))


if __name__ == "__main__":
    main()