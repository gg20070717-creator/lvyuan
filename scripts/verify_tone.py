"""真实环境验证 — 管家语气与交付方式（真实 DeepSeek API）。

检验「问题1：管家 AI 味重」的修复：
1. 问候 → 短、口语、无 AI 套话、不列点
2. 知识问答 → 口语化讲清考点，无套话
3. 生成讲义 → 交付语口语化（提学习中心 + 给精华），不再整篇贴回聊天
4. 生成计划 → 交付语给关键安排 + 学习中心指引
5. 资产链路回归（学习中心可见生成的资产）
"""

import re
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
USER = f"user_tone_{uuid.uuid4().hex[:8]}"
SESSION = f"session_tone_{uuid.uuid4().hex[:8]}"
results = []
passed = 0
failed = 0

# AI 味检测：高频套话 / 正式连接词
BANNED_PHRASES = ["好的，我来帮你", "作为一名", "首先，", "其次，", "综上所述", "希望对你有帮助", "我理解你的需求"]


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    results.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def hit(text: str, phrases) -> list[str]:
    return [p for p in phrases if p in (text or "")]


def send_message(payload, max_wait=480):
    with httpx.Client(timeout=30, trust_env=False) as c:
        enq = c.post(BASE + "/messages", json=payload)
        enq.raise_for_status()
        task_id = enq.json()["task_id"]
    deadline = time.time() + max_wait
    while time.time() < deadline:
        with httpx.Client(timeout=30, trust_env=False) as c:
            r = c.get(f"{BASE}/tasks/{task_id}")
            r.raise_for_status()
            task = r.json()
        if task["status"] == "completed":
            return task
        if task["status"] == "failed":
            raise RuntimeError(f"任务失败: {task['error']}")
        time.sleep(3)
    raise TimeoutError(f"任务 {task_id} 在 {max_wait}s 内未完成")


def timed_get(path, params=None, timeout=60):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.get(BASE + path, params=params)
        r.raise_for_status()
        return r.json()


# ── 1. 问候 ──
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION, "content": "你好，我想开始备考导游证"})
    text = resp["content"]
    dt = time.time() - t0
    banned = hit(text, BANNED_PHRASES)
    bullets = len(re.findall(r"^\s*[-*•]\s", text, re.M))
    ok = len(text) < 220 and not banned and bullets == 0
    report("问候：短句口语无套话不列点", ok,
           f"{dt:.1f}s · len={len(text)} · 套话={banned} · 列点={bullets}\n  回复：{text[:120]}")
except Exception as e:
    report("问候：短句口语无套话不列点", False, str(e))

# ── 2. 知识问答 ──
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION,
                         "content": "中国古典园林有哪些构景手法？"})
    text = resp["content"]
    dt = time.time() - t0
    banned = hit(text, BANNED_PHRASES)
    ok = len(text) > 30 and not banned and ("构景" in text or "手法" in text)
    report("知识问答：口语讲清考点无套话", ok,
           f"{dt:.1f}s · len={len(text)} · 套话={banned}\n  开头：{text[:100]}")
except Exception as e:
    report("知识问答：口语讲清考点无套话", False, str(e))

# ── 3. 生成讲义（交付语口语化 + 不整篇贴回 + 落资产 + 协同链路数据） ──
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION,
                         "content": "请帮我生成一份《突发事件应急处置》的学习讲义"})
    text = resp["content"]
    dt = time.time() - t0
    assets = resp.get("assets", [])
    banned = hit(text, BANNED_PHRASES)
    # 交付语应：提到学习中心 / 给出精华，且不是把整份讲义原文贴回（>1200 字视为整篇贴回）
    is_short_delivery = len(text) < 900
    ok = len(assets) >= 1 and ("学习中心" in text or "查看" in text) and is_short_delivery and not banned
    report("讲义交付：落资产 + 口语交付不贴全文", ok,
           f"{dt:.1f}s · assets={len(assets)} · len={len(text)} · 套话={banned}\n  开头：{text[:100]}")

    # 协同链路数据：内容生成 → 六帽审查（前端据此渲染「多智能体协同」）
    calls = resp.get("tool_calls", [])
    gen_first = "generate_material" in calls
    rev_after = "review_material" in calls and calls.index("generate_material") < calls.index("review_material")
    report("协同链路：生成→审查顺序 + 审查结论", gen_first and rev_after,
           f"tool_calls={calls} · review={resp.get('review', '')}")
except Exception as e:
    report("讲义交付：落资产 + 口语交付不贴全文", False, str(e))
    report("协同链路：生成→审查顺序 + 审查结论", False, str(e))

# ── 4. 生成计划（交付语给关键安排 + 学习中心） ──
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION, "content": "帮我制定一个备考计划"})
    text = resp["content"]
    dt = time.time() - t0
    assets = resp.get("assets", [])
    banned = hit(text, BANNED_PHRASES)
    ok = len(assets) >= 1 and len(text) < 900 and not banned
    report("计划交付：落资产 + 口语交付", ok,
           f"{dt:.1f}s · assets={len(assets)} · len={len(text)} · 套话={banned}\n  开头：{text[:100]}")
except Exception as e:
    report("计划交付：落资产 + 口语交付", False, str(e))

# ── 5. 资产链路回归 ──
try:
    rows = timed_get(f"/users/{USER}/assets")
    types = sorted({r["asset_type"] for r in rows["assets"]})
    report("回归：学习中心资产可见", rows["total"] >= 2 and "lecture" in types, f"total={rows['total']} types={types}")
except Exception as e:
    report("回归：学习中心资产可见", False, str(e))


print("\n===== 汇总 =====")
for r in results:
    print(r)
print(f"\n通过 {passed} / {passed + failed}")
raise SystemExit(0 if failed == 0 else 1)
