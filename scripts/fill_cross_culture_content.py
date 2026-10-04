# -*- coding: utf-8 -*-
"""用 Tokeness API 为跨文化知识库 L5 技能点填充 content（字数约 100~400，仅作提示词参考）。

设计要点（按用户要求）：
- 不依赖 AI 输出 JSON/固定格式 —— 每次调用只让 AI 返回一段纯文本正文，
  由本脚本直接写入现有 JSON 的 skill["content"] 字段（结构与教材知识库一致）。
- 字数「100~400」只写进提示词作为参考，不硬性校验、不因字数重试。
- 树（section.children）与顶层 skills[] 平铺数组在落盘时强制同步一致。
- 带实时进度条（百分比 / 已处理 / 成功失败 / token / ETA），支持断点续跑与按库/国家筛选。

用法:
  python -u scripts/fill_cross_culture_content.py --kb all --workers 10
  python -u scripts/fill_cross_culture_content.py --kb customs --countries us,jp --limit 5
  python -u scripts/fill_cross_culture_content.py --kb bridge --force   # 强制重填

配置（优先级：环境变量 > local.env > 默认值）:
  TOKENESS_API_KEY / TOKENESS_BASE_URL / TOKENESS_MODEL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LOCAL_ENV = ROOT / "local.env"
FILES = {
    "customs": DATA_DIR / "culture_customs_kb.json",
    "bridge": DATA_DIR / "cultural_bridge_kb.json",
}
DEFAULT_BASE = "https://n.tokeness.dev/v1"
DEFAULT_MODEL = "deepseek-v4-flash"


def load_local_env() -> dict:
    cfg = {}
    if LOCAL_ENV.exists():
        for line in LOCAL_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def get_cfg() -> dict:
    local = load_local_env()
    return {
        "api_key": os.environ.get("TOKENESS_API_KEY") or local.get("TOKENESS_API_KEY") or "",
        "base_url": os.environ.get("TOKENESS_BASE_URL") or local.get("TOKENESS_BASE_URL") or DEFAULT_BASE,
        "model": os.environ.get("TOKENESS_MODEL") or local.get("TOKENESS_MODEL") or DEFAULT_MODEL,
    }


def rebuild_flat(kb: dict) -> None:
    """让顶层 skills[] 平铺数组与树保持一致（同一批对象）。"""
    flat = []

    def walk(node: dict) -> None:
        if node["type"] == "skill":
            flat.append(node)
            return
        for c in node.get("children") or []:
            walk(c)

    walk(kb["root"])
    kb["skills"] = flat


def collect_tasks(kb: dict, kb_name: str, countries: set[str] | None, force: bool,
                  limit: int | None) -> list[tuple]:
    """返回 [(kb_name, skill, part_title, chapter_title, section_title), ...]（skill 为内存 kb 树里的引用）。"""
    tasks = []
    for part in kb["root"]["children"][0].get("children") or []:
        code = part["id"].split("__")[1]
        if countries and code not in countries:
            continue
        for ch in part.get("children") or []:
            for sec in ch.get("children") or []:
                for sk in sec.get("children") or []:
                    if sk["type"] != "skill":
                        continue
                    if not force and sk.get("content"):
                        continue
                    tasks.append((kb_name, sk, part["title"], ch["title"], sec["title"]))
    if limit:
        tasks = tasks[:limit]
    return tasks


def build_prompt(kb_name: str, part_title: str, chapter_title: str, section_title: str, skill_title: str) -> str:
    kb_label = "文化习惯知识" if kb_name == "customs" else "文化桥"
    return (
        f"你是跨文化知识库「{kb_label}」的内容作者。请为下面的技能点写一段中文正文。\n"
        f"要求：直接输出正文，不要标题、编号、列表、JSON、markdown 或任何前后缀说明；"
        f"内容准确、信息密度高；字数控制在100~400字之间，尽量300字左右（参考值，不用严格）。\n"
        f"背景：{part_title} ｜ 维度：{chapter_title} ｜ 主题：{section_title}\n"
        f"技能点：{skill_title}"
    )


def call_once(client: OpenAI, cfg: dict, prompt: str):
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=700,
    )
    usage = resp.usage
    tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0) if usage else 0
    return (resp.choices[0].message.content or "").strip(), tokens


def fill_one(client: OpenAI, cfg: dict, task: tuple, retries: int = 3) -> tuple:
    kb_name, skill, part_title, chapter_title, section_title = task
    title = skill["title"]
    last_err = ""
    for attempt in range(retries):
        try:
            text, tokens = call_once(client, cfg, build_prompt(kb_name, part_title, chapter_title, section_title, title))
            if text:
                skill["content"] = text
                return kb_name, skill["id"], True, len(text), tokens
            last_err = "空内容"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
    return kb_name, skill["id"], False, 0, 0


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_secs(s: float) -> str:
    s = int(s)
    return f"{s // 60}m{s % 60:02d}s"


def render_bar(done: int, total: int, ok: int, fail: int, tokens: int, t0: float) -> str:
    pct = done / total * 100 if total else 100
    bar_len = 20
    filled = int(bar_len * done / total) if total else bar_len
    bar = "█" * filled + "░" * (bar_len - filled)
    el = time.time() - t0
    eta = el / done * (total - done) if done else 0
    return (f"\r⏳ {pct:5.1f}% {bar} {done}/{total} "
            f"| 成功{ok} 失败{fail} | token≈{fmt_tokens(tokens)} "
            f"| 已用{fmt_secs(el)} | 预计还需{fmt_secs(eta)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", choices=["customs", "bridge", "all"], default="all")
    ap.add_argument("--countries", default="", help="逗号分隔的国家码，如 us,jp")
    ap.add_argument("--limit", type=int, default=None, help="最多填充条数（试跑用）")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--save-every", type=int, default=25)
    ap.add_argument("--force", action="store_true", help="强制重填已填内容的技能点")
    args = ap.parse_args()

    cfg = get_cfg()
    if not cfg["api_key"]:
        raise SystemExit("未找到 TOKENESS_API_KEY（请检查 local.env 或环境变量）")
    countries = {c.strip().lower() for c in args.countries.split(",") if c.strip()} or None

    kb_names = ["customs", "bridge"] if args.kb == "all" else [args.kb]
    kbs = {name: json.loads(FILES[name].read_text(encoding="utf-8")) for name in kb_names}

    all_tasks: list[tuple] = []
    for kb_name in kb_names:
        all_tasks.extend(collect_tasks(kbs[kb_name], kb_name, countries, args.force, args.limit))

    total = len(all_tasks)
    if total == 0:
        print("没有需要填充的技能点（可能已全部填完，可用 --force 重填）")
        return

    print(f"模型: {cfg['model']} | 待填充: {total} 条 | 并发: {args.workers} | 每{args.save_every}条落盘一次", flush=True)

    def save_now() -> None:
        for name in kb_names:
            rebuild_flat(kbs[name])  # 树 <-> skills[] 平铺同步
            FILES[name].write_text(json.dumps(kbs[name], ensure_ascii=False, indent=2), encoding="utf-8")

    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])

    state = {"done": 0, "ok": 0, "fail": 0, "tokens": 0}
    lock = threading.Lock()
    t0 = time.time()
    stop = threading.Event()

    def monitor():
        last = 0.0
        while not stop.is_set():
            time.sleep(2)
            with lock:
                if state["done"] != last:
                    sys.stdout.write(render_bar(state["done"], total, state["ok"], state["fail"], state["tokens"], t0))
                    sys.stdout.flush()
                    last = state["done"]

    mt = threading.Thread(target=monitor, daemon=True)
    mt.start()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fill_one, client, cfg, t): t for t in all_tasks}
        for fut in as_completed(futs):
            task = futs[fut]
            try:
                _kb, sid, ok_flag, n, tokens = fut.result()
            except Exception as e:  # noqa: BLE001
                with lock:
                    state["done"] += 1
                    state["fail"] += 1
                print(f"\n  [异常] {task[1]['title']}: {e}", flush=True)
                continue
            with lock:
                state["done"] += 1
                state["tokens"] += tokens
                if ok_flag:
                    state["ok"] += 1
                else:
                    state["fail"] += 1
                done = state["done"]
            if done % args.save_every == 0 or done == total:
                save_now()
                sys.stdout.write(render_bar(done, total, state["ok"], state["fail"], state["tokens"], t0) + "\n")
                sys.stdout.flush()

    stop.set()
    mt.join(timeout=5)
    save_now()

    # 自检：重读磁盘，确认树与平铺一致
    for name in kb_names:
        kb2 = json.loads(FILES[name].read_text(encoding="utf-8"))
        tree_filled = 0
        flat_filled = sum(1 for s in kb2["skills"] if s.get("content"))
        for part in kb2["root"]["children"][0].get("children") or []:
            for ch in part.get("children") or []:
                for sec in ch.get("children") or []:
                    tree_filled += sum(1 for s in sec.get("children") or [] if s.get("content"))
        print(f"  自检 [{name}] 树已填 {tree_filled} / 平铺已填 {flat_filled} / 共 {len(kb2['skills'])}", flush=True)

    el = time.time() - t0
    print(f"\n完成: 处理 {state['done']} | 成功 {state['ok']} | 失败 {state['fail']} | "
          f"累计token {fmt_tokens(state['tokens'])} | 耗时 {fmt_secs(el)}", flush=True)


if __name__ == "__main__":
    main()