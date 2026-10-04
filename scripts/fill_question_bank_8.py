# -*- coding: utf-8 -*-
"""为每个技能点补齐 8 道题（3 选择 + 3 判断 + 2 简答），缺失题目用 Tokeness API 生成。

- 每个最小技能点目标：3 选择 / 3 判断正误 / 2 简答 = 8 题；
- 已有选择超过 3 道 → 保留 3 道，超出部分作为生成种子并移出题库（转换为判断/简答）；
- 难度 1-4 确定性分配，保证每节点 4 个难度都有题目（不花 token 判断难易）；
- 生成用 Tokeness API（deepseek-v4-flash），断点续跑、每 N 节点落盘、实时进度条。

用法:
  python -u scripts/fill_question_bank_8.py --workers 10
  python -u scripts/fill_question_bank_8.py --limit 3        # 试跑
配置: local.env 的 TOKENESS_*
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

TARGET = {"选择": 3, "判断": 3, "简答": 2}
DIFF_CYCLE = [1, 2, 3, 4, 1, 2, 3, 4]


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


def load_kb():
    sys.path.insert(0, str(ROOT))
    from brain_of_cloud.knowledge.loader import KnowledgeBaseLoader
    return KnowledgeBaseLoader().load()


def skill_loc(skill) -> str:
    parts = list(getattr(skill, "path_titles", []) or [])
    return " / ".join(parts + [skill.title])


def build_prompt(skill, need, seed_choice):
    lines = ["你是导游/跨文化/入境游实战知识库的题库出题人。请为下面的技能点生成题目，直接输出题目，不要多余说明。",
             f"技能点：{skill.title}", f"所属：{skill_loc(skill)}",
             f"内容参考：{(skill.content or '')[:300]}"]
    if seed_choice:
        lines.append("以下为已有的选择题，可作为改编参考（不要重复）：\n" + "\n".join(f"- {c}" for c in seed_choice))
    need_lines = ["需要生成："]
    if need["选择"]:
        need_lines.append(f"- 选择题 {need['选择']} 道（四选一）")
    if need["判断"]:
        need_lines.append(f"- 判断题 {need['判断']} 道（陈述句，答 正确/错误）")
    if need["简答"]:
        need_lines.append(f"- 简答题 {need['简答']} 道（含参考答案与评分要点）")
    lines.append("\n".join(need_lines))
    lines.append(
        "严格按下面的格式输出（每道题之间空一行）：\n"
        "【选择】\n题目：<题干>\nA. <选项1>\nB. <选项2>\nC. <选项3>\nD. <选项4>\n答案：<A/B/C/D>\n解析：<50字内>\n"
        "【判断】\n题目：<陈述句>\n答案：<正确/错误>\n解析：<50字内>\n"
        "【简答】\n题目：<问题>\n参考答案：<要点>\n评分要点：<分条>\n"
    )
    return "\n".join(lines)


def parse_choice_block(block: str):
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    q = opts = ans = expl = None
    opt_pat = re.compile(r"^([A-Da-d])[.、．]\s*(.*)$")
    for ln in lines:
        if ln.startswith("题目"):
            q = re.sub(r"^题目[：:]\s*", "", ln)
        m = opt_pat.match(ln)
        if m:
            opts = opts if opts is not None else []
            opts.append(m.group(2).strip())
        if ln.startswith("答案"):
            ans = re.sub(r"^答案[：:]\s*", "", ln).strip().upper()
        if ln.startswith("解析"):
            expl = re.sub(r"^解析[：:]\s*", "", ln).strip()
    if not q or not opts or len(opts) < 4 or ans not in "ABCD" or not expl:
        return None
    return {"题目": q, "选项": opts[:4], "答案": ans, "解析": expl}


def parse_tf_block(block: str):
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    q = ans = expl = None
    for ln in lines:
        if ln.startswith("题目"):
            q = re.sub(r"^题目[：:]\s*", "", ln)
        if ln.startswith("答案"):
            ans = re.sub(r"^答案[：:]\s*", "", ln).strip()
        if ln.startswith("解析"):
            expl = re.sub(r"^解析[：:]\s*", "", ln).strip()
    if not q or not ans or not expl:
        return None
    ans = ans.replace("。", "").strip()
    if ans not in ("正确", "错误", "对", "错"):
        return None
    return {"题目": q, "答案": "A" if ans.startswith("正") or ans == "对" else "B", "解析": expl}


def parse_essay_block(block: str):
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    q = ref = rubric = None
    for ln in lines:
        if ln.startswith("题目"):
            q = re.sub(r"^题目[：:]\s*", "", ln)
        if ln.startswith("参考答案"):
            ref = re.sub(r"^参考答案[：:]\s*", "", ln).strip()
        if ln.startswith("评分要点"):
            rubric = re.sub(r"^评分要点[：:]\s*", "", ln).strip()
    if not q or not ref:
        return None
    return {"题目": q, "答案": ref, "解析": rubric or "", "选项": []}


def parse_response(text: str):
    sections = re.split(r"【(选择|判断|简答)】", text)
    res = {"选择": [], "判断": [], "简答": []}
    for i in range(1, len(sections) - 1, 2):
        kind, body = sections[i], sections[i + 1]
        if kind == "选择":
            for blk in re.split(r"\n\s*\n", body):
                item = parse_choice_block(blk)
                if item:
                    res["选择"].append(item)
        elif kind == "判断":
            for blk in re.split(r"\n\s*\n", body):
                item = parse_tf_block(blk)
                if item:
                    res["判断"].append(item)
        elif kind == "简答":
            for blk in re.split(r"\n\s*\n", body):
                item = parse_essay_block(blk)
                if item:
                    res["简答"].append(item)
    return res


def call_once(client, cfg, prompt):
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
        max_tokens=4000,
    )
    usage = resp.usage
    tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0) if usage else 0
    return (resp.choices[0].message.content or "").strip(), tokens


def gen_question_batch(client, cfg, skill, need, seed_choice, retries=3):
    last_err = ""
    for attempt in range(retries):
        try:
            text, tokens = call_once(client, cfg, build_prompt(skill, need, seed_choice))
            parsed = parse_response(text)
            ok = (len(parsed["选择"]) >= need["选择"]
                  and len(parsed["判断"]) >= need["判断"]
                  and len(parsed["简答"]) >= need["简答"])
            if ok:
                return parsed, tokens
            last_err = f"解析不足: 选{len(parsed['选择'])}判{len(parsed['判断'])}简{len(parsed['简答'])}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))
    return None, 0


def finalize_node(questions, existing, parsed, need, skill):
    """把生成结果写入题库：保留 3 道已有选择（超出移除），追加生成题，难度 1-4 全覆盖。"""
    choice_existing = [q for q in existing if q.get("类型", "选择") == "选择"]
    excess = choice_existing[3:]
    for q in excess:
        if q in questions:
            questions.remove(q)
    kept_diffs = {int(q.get("难度", 3)) for q in choice_existing[:3]}

    loc = skill_loc(skill)
    new_entries = []
    for item in parsed["选择"][: need["选择"]]:
        new_entries.append({**item, "类型": "选择", "章-节-点": loc})
    for item in parsed["判断"][: need["判断"]]:
        new_entries.append({"题目": item["题目"], "选项": ["正确", "错误"], "答案": item["答案"],
                            "解析": item["解析"], "类型": "判断", "章-节-点": loc})
    for item in parsed["简答"][: need["简答"]]:
        new_entries.append({"题目": item["题目"], "选项": [], "答案": item["答案"],
                            "解析": item["解析"], "类型": "简答", "章-节-点": loc})

    for i, e in enumerate(new_entries):
        e["难度"] = DIFF_CYCLE[i % 8]
    covered = kept_diffs | {int(e["难度"]) for e in new_entries}
    for d in (1, 2, 3, 4):
        if d not in covered and new_entries:
            new_entries[-1]["难度"] = d
            covered.add(d)
    questions.extend(new_entries)
    return len(new_entries)


def fmt_secs(s):
    s = int(s)
    return f"{s // 60}m{s % 60:02d}s"


def render_bar(done, total, ok, fail, tokens, t0):
    pct = done / total * 100 if total else 100
    filled = int(20 * done / total) if total else 20
    bar = "#" * filled + "-" * (20 - filled)
    el = time.time() - t0
    eta = el / done * (total - done) if done else 0
    return (f"\r[{pct:5.1f}%] {bar} {done}/{total} | ok={ok} fail={fail} | tok~{tokens//1000}K "
            f"| el={fmt_secs(el)} | eta={fmt_secs(eta)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--save-every", type=int, default=20)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--suffix", default=None, help="只处理技能点标题以该后缀结尾的节点（如 ·民俗风情）")
    args = ap.parse_args()

    cfg = get_cfg()
    if not cfg["api_key"]:
        raise SystemExit("未找到 TOKENESS_API_KEY（请检查 local.env）")

    kb = load_kb()
    bank = json.loads(BANK_FILE.read_text(encoding="utf-8"))
    questions = bank.setdefault("questions", [])

    by_skill: dict[str, list[dict]] = {}
    for q in questions:
        loc = q.get("章-节-点", "")
        parts = [p.strip() for p in re.split(r"\s+/\s+", loc) if p.strip()]
        title = parts[-1] if parts else ""
        skills = kb.skills_by_title.get(title, [])
        sid = skills[0].id if skills else None
        if sid:
            by_skill.setdefault(sid, []).append(q)

    tasks = []
    for sk in kb.skills:
        if args.suffix and not sk.title.endswith(args.suffix):
            continue
        existing = by_skill.get(sk.id, [])
        counts = {"选择": 0, "判断": 0, "简答": 0}
        for q in existing:
            counts[q.get("类型", "选择")] = counts.get(q.get("类型", "选择"), 0) + 1
        need = {t: max(0, TARGET[t] - counts[t]) for t in TARGET}
        if args.force or any(need.values()):
            tasks.append((sk, existing, counts, need))
    if args.limit:
        tasks = tasks[: args.limit]
    total = len(tasks)
    if total == 0:
        print("所有技能点已达标（3选择/3判断/2简答）")
        return

    print(f"模型: {cfg['model']} | 待处理技能点: {total} | 并发: {args.workers}", flush=True)

    def save_now():
        bank["total"] = len(questions)
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

    def work(task):
        sk, existing, counts, need = task
        seed = [q["题目"] for q in existing if q.get("类型") == "选择"][:2]
        parsed, tokens = gen_question_batch(client, cfg, sk, need, seed)
        if parsed is None:
            return sk.id, False, None, tokens
        return sk.id, True, parsed, tokens

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, t): t for t in tasks}
        pending = {}
        for fut in as_completed(futs):
            task = futs[fut]
            try:
                sid, ok_flag, parsed, tokens = fut.result()
            except Exception as e:  # noqa: BLE001
                with lock:
                    state["done"] += 1
                    state["fail"] += 1
                print(f"\n  [异常] {task[0].title}: {e}", flush=True)
                continue
            with lock:
                state["done"] += 1
                state["tokens"] += tokens
                if ok_flag:
                    state["ok"] += 1
                else:
                    state["fail"] += 1
                done = state["done"]
            if ok_flag:
                pending[sid] = (task, parsed)
            if done % args.save_every == 0 or done == total:
                for sid2, (task2, parsed2) in list(pending.items()):
                    sk, existing, counts, need = task2
                    finalize_node(questions, existing, parsed2, need, sk)
                    pending.pop(sid2, None)
                save_now()
                sys.stdout.write(render_bar(done, total, state["ok"], state["fail"], state["tokens"], t0) + "\n")
                sys.stdout.flush()
        # 收尾：处理剩余 pending
        for sid2, (task2, parsed2) in list(pending.items()):
            sk, existing, counts, need = task2
            finalize_node(questions, existing, parsed2, need, sk)
            pending.pop(sid2, None)

    stop.set()
    mt.join(timeout=5)
    save_now()
    el = time.time() - t0
    print(f"\n完成: 处理 {state['done']} | 成功 {state['ok']} | 失败 {state['fail']} | token {state['tokens']} | 耗时 {fmt_secs(el)}", flush=True)


if __name__ == "__main__":
    main()