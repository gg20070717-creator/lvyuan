# -*- coding: utf-8 -*-
"""为「入境游实战能力」129 个技能点填充 content（注意事项式，~800字，联网搜索）+ key_points。

- 模型：kimi-k3（支持联网搜索；deepseek 系不支持 web_search 工具，本脚本按模型名自动判断）
- content：AI 联网检索最新信息后写的实战注意事项（怎么做/注意什么/别踩雷），800字左右（不严格）
- key_points：3~5 条可判定要点（「要点：」行），供沙盒评分 AI 逐条判定
- 断点续跑、每 N 条落盘、实时进度条

用法:
  python -u scripts/fill_inbound_practice_content.py --workers 8
  python -u scripts/fill_inbound_practice_content.py --limit 2   # 试跑
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOCAL_ENV = ROOT / "local.env"
KB_FILE = DATA / "inbound_practice_kb.json"
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


def collect_tasks(kb: dict, force: bool, limit: int | None) -> list[tuple]:
    tasks = []
    for part in kb["root"]["children"][0].get("children") or []:
        for ch in part.get("children") or []:
            for sec in ch.get("children") or []:
                for sk in sec.get("children") or []:
                    if sk["type"] != "skill":
                        continue
                    if not force and sk.get("content"):
                        continue
                    tasks.append((sk, part["title"], ch["title"], sec["title"]))
    if limit:
        tasks = tasks[:limit]
    return tasks


def build_prompt(part_title, ch_title, sec_title, skill_title, hint=""):
    return (
        "你是「入境游实战能力」知识库的内容作者。请先联网检索与本题相关的最新信息，再为下面的技能点写一段中文正文。\n"
        "要求：\n"
        "1. 涉及政策/规则/平台机制的内容（如免签、退税、涉外资格、支付、TripAdvisor/Google留评等）务必以最新情况为准；\n"
        "2. 这是给导游/定制师看的实战注意事项，不是知识介绍——重点写：注意什么、怎么做、别踩什么雷、关键步骤或话术；\n"
        "3. 直接输出正文，字数800字左右（参考值，多些少些都行，不用严格），不要标题、编号、JSON、markdown；\n"
        "4. 正文写完后，另起一行输出3~5条评分要点，每行以「要点：」开头（供沙盒AI逐条判定学员是否做到）。\n"
        "\n"
        f"阶段：{part_title} ｜ 维度：{ch_title} ｜ 主题：{sec_title}\n"
        f"技能点：{skill_title}"
        + (f"\n（注意：上次输出格式不对或内容过短，请严格按要求输出）" if hint else "")
    )


def parse(text: str):
    lines = [ln.strip() for ln in text.splitlines()]
    kps, content_lines = [], []
    for ln in lines:
        if ln.startswith("要点") or ln.startswith("关键点") or ln.startswith("评分要点"):
            m = re.sub(r"^(要点|关键点|评分要点)[：:]\s*", "", ln)
            if m:
                kps.append(m)
        else:
            content_lines.append(ln)
    return "\n".join(content_lines).strip(), kps


def call_once(client, cfg, prompt):
    kwargs = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 6000,
    }
    if "kimi" in cfg["model"].lower():
        kwargs["tools"] = [{"type": "web_search"}]
    resp = client.chat.completions.create(**kwargs)
    usage = resp.usage
    tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0) if usage else 0
    return (resp.choices[0].message.content or "").strip(), tokens


def fill_one(client, cfg, task, retries=3):
    sk, part_title, ch_title, sec_title = task
    last_err = ""
    for attempt in range(retries):
        try:
            text, tokens = call_once(client, cfg, build_prompt(part_title, ch_title, sec_title, sk["title"], hint=last_err))
            content, kps = parse(text)
            if len(content) >= 50 and 3 <= len(kps) <= 6:
                sk["content"] = content
                sk["key_points"] = kps
                return True, len(content), len(kps), tokens
            last_err = f"内容{len(content)}字/要点{len(kps)}条"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
    return False, 0, 0, 0


def fmt_secs(s):
    s = int(s)
    return f"{s // 60}m{s % 60:02d}s"


def render_bar(done, total, ok, fail, tokens, t0):
    pct = done / total * 100 if total else 100
    filled = int(20 * done / total) if total else 20
    bar = "█" * filled + "░" * (20 - filled)
    el = time.time() - t0
    eta = el / done * (total - done) if done else 0
    return (f"\r⏳ {pct:5.1f}% {bar} {done}/{total} | 成功{ok} 失败{fail} | token≈{tokens//1000}K "
            f"| 已用{fmt_secs(el)} | 预计还需{fmt_secs(eta)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--save-every", type=int, default=10)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = get_cfg()
    if not cfg["api_key"]:
        raise SystemExit("未找到 TOKENESS_API_KEY（请检查 local.env）")
    kb = json.loads(KB_FILE.read_text(encoding="utf-8"))
    tasks = collect_tasks(kb, args.force, args.limit)
    total = len(tasks)
    if total == 0:
        print("没有需要填充的技能点（可能已全部填完）")
        return

    print(f"模型: {cfg['model']} | 联网搜索: {'是' if 'kimi' in cfg['model'].lower() else '否'} | 待填充: {total} 条 | 并发: {args.workers}", flush=True)

    def save_now():
        flat = []
        def walk(n):
            if n["type"] == "skill":
                flat.append(n); return
            for c in n.get("children") or []:
                walk(c)
        walk(kb["root"])
        kb["skills"] = flat
        KB_FILE.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")

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
        futs = {ex.submit(fill_one, client, cfg, t): t for t in tasks}
        for fut in as_completed(futs):
            task = futs[fut]
            try:
                ok_flag, n, nk, tokens = fut.result()
            except Exception as e:  # noqa: BLE001
                with lock:
                    state["done"] += 1; state["fail"] += 1
                print(f"\n  [异常] {task[0]['title']}: {e}", flush=True)
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

    kb2 = json.loads(KB_FILE.read_text(encoding="utf-8"))
    filled = sum(1 for s in kb2["skills"] if s.get("content"))
    with_kp = sum(1 for s in kb2["skills"] if s.get("key_points"))
    lens = [len(s.get("content") or "") for s in kb2["skills"] if s.get("content")]
    print(f"\n自检: 技能点 {len(kb2['skills'])} | 有内容 {filled} | 有key_points {with_kp} | "
          f"内容字数 min/avg/max = {min(lens) if lens else 0}/{sum(lens)//len(lens) if lens else 0}/{max(lens) if lens else 0}", flush=True)
    print(f"完成: 处理 {state['done']} | 成功 {state['ok']} | 失败 {state['fail']} | token {state['tokens']} | 耗时 {fmt_secs(time.time()-t0)}", flush=True)


if __name__ == "__main__":
    main()