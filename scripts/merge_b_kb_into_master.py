#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 0.1.0(B) 的领域知识库 book 并入主线(A) master_knowledge_base.json。

处理：
1) B 的 guide/customizer 是 chapter->skill（无 section），先插入 section 层对齐 A 结构；
2) 书节点 parentId -> A root；整树 childIds/parentId 修正；
3) book.stats / root.stats 重算；冲突 id 检查；
4) 备份原文件到 .pytest_tmp（已 gitignore），再原子替换写入。

用法：
  python scripts/merge_b_kb_into_master.py --dry-run
  python scripts/merge_b_kb_into_master.py
"""
import argparse
import copy
import json
import os
import shutil
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MASTER = os.path.join(ROOT, "data", "master_knowledge_base.json")
DEFAULT_KB_DIR = r"D:/BrainOfCloud-master/BrainOfCloud-0.1.0/data"
FILES = ["kb_guide_practice.json", "kb_customizer.json", "kb_inbound.json"]


def walk(node):
    yield node
    for c in node.get("children") or []:
        yield from walk(c)


def collect_ids(root) -> set:
    ids = set()
    for n in walk(root):
        ids.add(n.get("id"))
    return ids


def count_types(root) -> Counter:
    cnt = Counter()
    for n in walk(root):
        if n.get("type"):
            cnt[n["type"]] += 1
    return cnt


def fix_stats(node):
    cnt = count_types(node)
    node["stats"] = {
        "title": node.get("title", ""),
        "parts": cnt.get("part", 0),
        "chapters": cnt.get("chapter", 0),
        "sections": cnt.get("section", 0),
        "skills": cnt.get("skill", 0),
    }


def adapt_chapters(book, master_id):
    """为 chapter 直挂 skill 的情况插入 section；修正 parentId。返回 skill->newParent 映射。"""
    mapping = {}
    for n in walk(book):
        if n.get("type") == "skill":
            # 树内 skill 的 parentId 后续统一由映射决定
            pass
    # 先收集所有需包装的 chapter
    def rec(node):
        if node.get("type") == "chapter":
            kids = node.get("children") or []
            direct = [k for k in kids if k.get("type") == "skill"]
            rest = [k for k in kids if k.get("type") != "skill"]
            if direct:
                sid = node["id"] + "__s"
                sec = {
                    "id": sid,
                    "type": "section",
                    "title": "技能要点",
                    "content": "",
                    "parentId": node["id"],
                    "children": copy.deepcopy(direct),
                    "childIds": [d["id"] for d in direct],
                    "stats": {"skills": len(direct)},
                }
                for d in sec["children"]:
                    d["parentId"] = sid
                    mapping[d["id"]] = sid
                node["children"] = rest + [sec]
                node["childIds"] = [c["id"] for c in node["children"]]
        for c in node.get("children") or []:
            rec(c)
    rec(book)
    # book 顶层 parentId 修正
    book["parentId"] = master_id
    return mapping


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", default=DEFAULT_MASTER)
    ap.add_argument("--kb-dir", default=DEFAULT_KB_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.master, encoding="utf-8") as f:
        master = json.load(f)
    root = master["root"]
    master_id = root["id"]

    before_ids = collect_ids(root)
    before_ids |= {s["id"] for s in master.get("skills", [])}
    before_skills = len(master.get("skills", []))
    before_books = sum(1 for c in root.get("children", []) if c.get("type") == "book")

    new_books = []
    new_skills = []
    added = 0
    for name in FILES:
        path = os.path.join(args.kb_dir, name)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        broot = data.get("root", {})
        books = [b for b in (broot.get("children") or []) if b.get("type") == "book"]
        print("[file] %-28s books=%d" % (name, len(books)))
        file_sub_ids = set()
        mapping_all = {}
        for book in books:
            bid = book.get("id")
            if bid in before_ids:
                raise SystemExit("book id 冲突: %s" % bid)
            sub_ids = collect_ids(book)
            dup = sub_ids & before_ids
            if dup:
                raise SystemExit("子树 id 冲突(%s): %s" % (bid, sorted(dup)[:5]))
            mapping = adapt_chapters(book, master_id)
            mapping_all.update(mapping)
            fix_stats(book)
            new_books.append(book)
            before_ids |= sub_ids
            file_sub_ids |= sub_ids
            added += 1
        # 该文件 flat skills（同文件 tree 含 skill 镜像节点，不与自身判冲突）
        for s in data.get("skills", []):
            sid = s.get("id")
            if sid in mapping_all:
                s = dict(s)
                s["parentId"] = mapping_all[sid]
            if sid in before_ids and sid not in file_sub_ids:
                raise SystemExit("flat skill 跨文件/跨库冲突: %s" % sid)
            if sid not in file_sub_ids:
                raise SystemExit("flat skill 不在树内(parent 链会断): %s" % sid)
            new_skills.append(s)
            before_ids.add(sid)

    print("== 将新增 books=%d, skills=%d (原 books=%d, skills=%d) ==" % (added, len(new_skills), before_books, before_skills))

    if args.dry_run:
        print("dry-run：不写文件。")
        return

    # 备份（放系统临时目录，避免进 git）
    import tempfile
    bak = os.path.join(tempfile.gettempdir(), "master_knowledge_base.pre-0.1.0-merge.json")
    shutil.copy2(args.master, bak)
    print("备份:", bak)

    root["children"] = (root.get("children") or []) + new_books
    root["childIds"] = [c.get("id") for c in root["children"] if c.get("id")]
    master["skills"] = (master.get("skills") or []) + new_skills
    fix_stats(root)

    tmp = args.master + ".new"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False)
    os.replace(tmp, args.master)
    print("写入完成：books=%d, skills=%d" % (
        sum(1 for c in root["children"] if c.get("type") == "book"), len(master["skills"])))


if __name__ == "__main__":
    main()