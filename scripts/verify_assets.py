"""真实环境验证 — 文件资产全链路（真实 DeepSeek API）。

验证 4 大用户路径：
1. 对话生成讲义 → 响应提示已保存 → 学习中心出现「讲义」资产
2. 对话生成学习计划 → 出现「学习计划」资产
3. 工具箱生成计划/报告 → 落库为资产
4. 学习中心：列表 / 类型过滤 / 详情 / 删除 / 404 边界
5. 回归：知识库浏览、真题判分、用户状态

前置：后端已在 http://127.0.0.1:8000 启动（真实 API）。
"""

import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
USER = f"user_asset_{uuid.uuid4().hex[:8]}"
SESSION = f"session_asset_{uuid.uuid4().hex[:8]}"
results = []
passed = 0
failed = 0


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    results.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def timed_get(path, params=None, timeout=60):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.get(BASE + path, params=params)
        r.raise_for_status()
        return r.json()


def timed_post(path, payload, timeout=240):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.post(BASE + path, json=payload)
        r.raise_for_status()
        return r.json()


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


# ── 0. 健康 + 空资产列表 ──
try:
    report("健康检查", timed_get("/").get("status") == "ok")
except Exception as e:
    report("健康检查", False, str(e))

try:
    rows = timed_get(f"/users/{USER}/assets")
    report("学习中心：新用户空列表", rows["total"] == 0, f"total={rows['total']}")
except Exception as e:
    report("学习中心：新用户空列表", False, str(e))

# ── 1. 对话生成讲义（长路径 generate_material + 六帽审查）→ 资产 ──
try:
    t0 = time.time()
    resp = send_message({
        "user_id": USER, "session_id": SESSION,
        "content": "请帮我生成一份《突发事件应急处置》的学习讲义，涵盖应急处置制度、应急响应级别和处置流程",
    })
    dt = time.time() - t0
    ok = len(resp["content"]) > 50 and "学习中心" in resp["content"]
    report("对话生成讲义 → 提示已保存学习中心", ok,
           f"{dt:.1f}s · assets={len(resp.get('assets', []))} · 尾部含学习中心={ '学习中心' in resp['content'] }")
except Exception as e:
    report("对话生成讲义 → 提示已保存学习中心", False, str(e))

# ── 2. 对话生成学习计划 → 资产 ──
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION, "content": "帮我制定一个导游证备考学习计划"})
    dt = time.time() - t0
    types = [a["asset_type"] for a in resp.get("assets", [])]
    ok = "plan" in types
    report("对话生成学习计划 → plan 资产", ok, f"{dt:.1f}s · types={types}")
except Exception as e:
    report("对话生成学习计划 → plan 资产", False, str(e))

# ── 3. 工具箱生成计划 / 报告 → 资产 ──
try:
    plan = timed_post("/training/plan", {"user_id": USER}, timeout=120)
    report("工具箱：生成学习计划", len(plan.get("plan", "")) > 20, f"len={len(plan.get('plan', ''))}")
except Exception as e:
    report("工具箱：生成学习计划", False, str(e))

try:
    rpt = timed_post("/training/report", {"user_id": USER}, timeout=120)
    report("工具箱：生成学习报告", rpt["report"]["recommended_action"] is not None)
except Exception as e:
    report("工具箱：生成学习报告", False, str(e))

# ── 4. 学习中心列表 / 过滤 / 详情 / 删除 / 404 ──
try:
    rows = timed_get(f"/users/{USER}/assets")
    types = [r["asset_type"] for r in rows["assets"]]
    ok = rows["total"] >= 3 and "lecture" in types and "plan" in types and "report" in types
    report("学习中心：列表含讲义/计划/报告", ok, f"total={rows['total']} types={sorted(set(types))}")
except Exception as e:
    report("学习中心：列表含讲义/计划/报告", False, str(e))

try:
    plans = timed_get(f"/users/{USER}/assets", params={"asset_type": "plan"})
    report("学习中心：类型过滤 plan", plans["total"] >= 1 and all(r["asset_type"] == "plan" for r in plans["assets"]),
           f"plan_total={plans['total']}")
except Exception as e:
    report("学习中心：类型过滤 plan", False, str(e))

try:
    rows = timed_get(f"/users/{USER}/assets")
    aid = rows["assets"][0]["asset_id"]
    detail = timed_get(f"/assets/{aid}")
    ok = detail["asset_id"] == aid and len(detail["content"]) > 20 and detail["title"]
    report("学习中心：查看资产详情", ok, f"title={detail['title']} type={detail['asset_type']} content_len={len(detail['content'])}")
except Exception as e:
    report("学习中心：查看资产详情", False, str(e))

try:
    rows = timed_get(f"/users/{USER}/assets")
    aid = rows["assets"][-1]["asset_id"]
    with httpx.Client(timeout=30, trust_env=False) as c:
        r = c.delete(f"{BASE}/assets/{aid}")
    ok1 = r.status_code == 200
    with httpx.Client(timeout=30, trust_env=False) as c:
        r2 = c.get(f"{BASE}/assets/{aid}")
    ok2 = r2.status_code == 404
    with httpx.Client(timeout=30, trust_env=False) as c:
        r3 = c.delete(f"{BASE}/assets/{aid}")
    ok3 = r3.status_code == 404
    report("学习中心：删除资产 → 删除后 404", ok1 and ok2 and ok3, f"delete={ok1} get_after={ok2} delete_again={ok3}")
except Exception as e:
    report("学习中心：删除资产 → 删除后 404", False, str(e))

try:
    with httpx.Client(timeout=30, trust_env=False) as c:
        r = c.get(f"{BASE}/assets/no_such_asset")
    report("边界：未知资产 404", r.status_code == 404, f"status={r.status_code}")
except Exception as e:
    report("边界：未知资产 404", False, str(e))

# ── 5. 回归：知识库 / 训练判分 / 用户状态 ──
try:
    books = timed_get("/knowledge/books")
    report("回归：知识库 4 本 713 技能点", books["stats"]["books"] == 4 and books["stats"]["skills"] == 713)
except Exception as e:
    report("回归：知识库", False, str(e))

try:
    quiz = timed_post("/training/random", {"knowledge_point_ids": [], "difficulty": "", "limit": 1})
    q = quiz["questions"][0]
    r = timed_post("/training/submissions", {"user_id": USER, "question_id": q["question_id"], "answer": q["answer"]})
    report("回归：真题判分", r["correct"] is True)
except Exception as e:
    report("回归：真题判分", False, str(e))

try:
    state = timed_get(f"/users/{USER}/state")
    report("回归：用户状态", state["stats"]["total_skills"] == 713 and "weak_point_titles" in state)
except Exception as e:
    report("回归：用户状态", False, str(e))


print("\n===== 汇总 =====")
for r in results:
    print(r)
print(f"\n通过 {passed} / {passed + failed}")
raise SystemExit(0 if failed == 0 else 1)
