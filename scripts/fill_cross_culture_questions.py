# -*- coding: utf-8 -*-
"""为跨文化知识库 2520 个技能点各生成 1 道四选一真题，直接合并进 master_question_bank.json。

- 完全照现有题库格式：{题目, 选项[4], 章-节-点, 答案, 解析}；
- 章-节-点 = 「书名 / 国家(桥) / 维度 / 主题 / 技能点标题」，loader 按最后一段精确匹配；
- 出题只依赖 AI 输出「题目/A.B.C.D./答案/解析」的行式文本，脚本解析后写入现有格式（不依赖 AI 输出 JSON）；
- 断点续跑：题库里已有该技能点题目的自动跳过；每 N 条落盘一次；带实时进度条。

用法:
  python -u scripts/fill_cross_culture_questions.py --workers 10
  python -u scripts/fill_cross_culture_questions.py --limit 5          # 试跑
  python -u scripts/fill_cross_culture_questions.py --countries us,jp  # 只做部分国家

配置（优先级：环境变量 > local.env > 默认值）:
  TOKENESS_API_KEY / TOKENESS_BASE_URL / TOKENESS_MODEL
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
KB_FILE = DATA / "master_knowledge_base.json"
BANK_FILE = DATA / "master_question_bank.json"
DEFAULT_BASE = "https://n.tokeness.dev/v1"
DEFAULT_MODEL = "deepseek-v4-flash"

_OPT_PREFIX = re.compile(r"^[A-Da-d][.、．]\s*")


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


def collect_cross_culture_skills(kb: dict, countries: set[str] | None) -> list[dict]:
    """返回跨文化技能点上下文列表。"""
    out = []
    for book in kb["root"]["children"]:
        if book["title"] not in ("文化习惯知识", "文化桥"):
            continue
        for part in book.get("children") or []:
            code = part["id"].split("__")[1]
            if countries and code not in countries:
                continue
            for ch in part.get("children") or []:
                for sec in ch.get("children") or []:
                    for sk in sec.get("children") or []:
                        if sk["type"] != "skill":
                            continue
                        out.append({
                            "book": book["title"], "part": part["title"],
                            "chapter": ch["title"], "section": sec["title"],
                            "skill": sk,
                        })
    return out


def build_prompt(ctx: dict, hint: str = "") -> str:
    sk = ctx["skill"]
    return (
        "你是导游资格证考试题库的出题人。请根据下面的跨文化知识点出一道四选一选择题。\n"
        "要求：题干清楚、选项唯一正确、答案与解析准确；解析50字以内。\n"
        "严格按下面的格式输出，不要输出任何多余内容：\n"
        "题目：<题干>\n"
        "A. <选项1>\n"
        "B. <选项2>\n"
        "C. <选项3>\n"
        "D. <选项4>\n"
        "答案：<A/B/C/D>\n"
        "解析：<50字以内>\n"
        "\n"
        f"知识库：{ctx['book']}\n"
        f"国家/桥梁：{ctx['part']}\n"
        f"维度：{ctx['chapter']}\n"
        f"主题：{ctx['section']}\n"
        f"技能点：{sk['title']}\n"
        f"内容：{sk.get('content') or ''}"
        + (f"\n（注意：上次输出格式不对，请严格按「题目/A. B. C. D./答案/解析」格式输出）" if hint else "")
    )


def parse_question(text: str) -> dict | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    q = opts = ans = expl = None
    opt_pat = re.compile(r"^([A-Da-d])[.、．]\s*(.*)$")
    for ln in lines:
        if ln.startswith("题目") or ln.startswith("题干"):
            q = re.sub(r"^题目[：:]\s*", "", ln)
        m = opt_pat.match(ln)
        if m and opts is not None and len(opts) < 4:
            opts.append(m.group(2).strip())
        if ln.startswith("答案"):
            ans = re.sub(r"^答案[：:]\s*", "", ln).strip().upper()
        if ln.startswith("解析"):
            expl = re.sub(r"^解析[：:]\s*", "", ln).strip()
        if ln.startswith("A.") or ln.startswith("A．") or ln.startswith("A、"):  # 选项行
            if opts is None:
                opts = []
            m2 = opt_pat.match(ln)
            if m2:
                opts.append(m2.group(2).strip())
    if opts is None:
        opts = []
    if not q or len(opts) != 4 or not ans or ans not in "ABCD" or not expl:
        return None
    return {"题目": q, "选项": opts, "答案": ans, "解析": expl}


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


def gen_question(client: OpenAI, cfg: dict, ctx: dict, retries: int = 3) -> tuple:
    title = ctx["skill"]["title"]
    last_err = ""
    for attempt in range(retries):
        try:
            text, tokens = call_once(client, cfg, build_prompt(ctx, hint=last_err))
            parsed = parse_question(text)
            if parsed:
                parsed["章-节-点"] = f"{ctx['book']} / {ctx['part']} / {ctx['chapter']} / {ctx['section']} / {title}"
                return parsed, True, tokens
            last_err = "格式不对"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
    return None, False, 0


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
    ap.add_argument("--countries", default="", help="逗号分隔的国家码，如 us,jp")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--save-every", type=int, default=25)
    ap.add_argument("--force", action="store_true", help="强制重做已配题的技能点")
    args = ap.parse_args()

    cfg = get_cfg()
    if not cfg["api_key"]:
        raise SystemExit("未找到 TOKENESS_API_KEY（请检查 local.env 或环境变量）")
    countries = {c.strip().lower() for c in args.countries.split(",") if c.strip()} or None

    kb = json.loads(KB_FILE.read_text(encoding="utf-8"))
    bank = json.loads(BANK_FILE.read_text(encoding="utf-8"))
    questions = bank.setdefault("questions", [])

    # 已覆盖的技能点标题（章-节-点 最后一段）
    covered = set()
    for q in questions:
        loc = q.get("章-节-点", "")
        parts = [p.strip() for p in loc.split("/") if p.strip()]
        if parts:
            covered.add(parts[-1])

    ctxs = [c for c in collect_cross_culture_skills(kb, countries)
            if args.force or c["skill"]["title"] not in covered]
    if args.limit:
        ctxs = ctxs[: args.limit]

    total = len(ctxs)
    if total == 0:
        print("没有需要配题的跨文化技能点（可能已全部配过，可用 --force 重做）")
        return

    print(f"模型: {cfg['model']} | 待配题: {total} 条 | 并发: {args.workers} | 每{args.save_every}条落盘一次", flush=True)

    def save_now() -> None:
        bank["total"] = len(questions)
        bank["targetSkills"] = len({q.get("章-节-点", "").split("/")[-1].strip() for q in questions})
        BANK_FILE.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")

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
        futs = {ex.submit(gen_question, client, cfg, c): c for c in ctxs}
        for fut in as_completed(futs):
            ctx = futs[fut]
            try:
                parsed, ok_flag, tokens = fut.result()
            except Exception as e:  # noqa: BLE001
                with lock:
                    state["done"] += 1
                    state["fail"] += 1
                print(f"\n  [异常] {ctx['skill']['title']}: {e}", flush=True)
                continue
            with lock:
                state["done"] += 1
                state["tokens"] += tokens
                if ok_flag and parsed:
                    questions.append(parsed)
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

    # 自检
    bank2 = json.loads(BANK_FILE.read_text(encoding="utf-8"))
    qs2 = bank2["questions"]
    cc = [q for q in qs2 if q["章-节-点"].startswith(("文化习惯知识", "文化桥"))]
    print(f"\n自检: 题库总数 {len(qs2)} | 其中跨文化 {len(cc)} | total={bank2['total']} targetSkills={bank2['targetSkills']}", flush=True)

    el = time.time() - t0
    print(f"完成: 处理 {state['done']} | 成功 {state['ok']} | 失败 {state['fail']} | "
          f"累计token {fmt_tokens(state['tokens'])} | 耗时 {fmt_secs(el)}", flush=True)


if __name__ == "__main__":
    main()