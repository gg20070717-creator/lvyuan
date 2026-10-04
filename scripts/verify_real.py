"""真实环境验证 — 走完整用户路径（真实 DeepSeek API）。

覆盖路径：
1. 健康检查
2. 知识库浏览（树/搜索/详情/题库）
3. 用户状态（空）
4. 创建画像 → 记忆沉淀
5. 真题测验 + 判分（对/错）
6. 真实对话：问候（无工具）
7. 真实对话：知识问答（触发 search_knowledge）
8. 真实对话：学习计划（触发 generate_plan）
9. 真实对话：生成讲义 + 六帽审查（触发 generate_material + review_material）
10. 最终用户状态（掌握度/薄弱点/记忆）
"""

import json
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
USER = f"user_real_{uuid.uuid4().hex[:8]}"
SESSION = f"session_real_{uuid.uuid4().hex[:8]}"
results = []
passed = 0
failed = 0


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    mark = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    results.append(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def timed_post(path, payload, timeout=240):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.post(BASE + path, json=payload)
        r.raise_for_status()
        return r.json()


def timed_get(path, params=None, timeout=60):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.get(BASE + path, params=params)
        r.raise_for_status()
        return r.json()


def send_message(payload, max_wait=480):
    """异步对话：入队 → 轮询直到 completed / failed。"""
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


# 1. 健康
try:
    ok = timed_get("/").get("status") == "ok"
    report("健康检查", ok)
except Exception as e:
    report("健康检查", False, str(e))

# 2. 知识库浏览
try:
    books = timed_get("/knowledge/books")
    report("知识库：4 本书 713 技能点", books["stats"]["books"] == 4 and books["stats"]["skills"] == 713,
           f"books={books['stats']['books']} skills={books['stats']['skills']}")
    tree = timed_get("/knowledge/tree")["tree"]
    report("知识库：目录树", len(tree) == 4)
    search = timed_get("/knowledge/search", params={"q": "突发事件应急处置", "top_k": 3})
    top = search["results"][0] if search["results"] else {}
    report("知识库：检索命中", search["count"] >= 1 and "政策与法律法规" in top.get("source", ""),
           f"top={top.get('title')} src={top.get('source')}")
    skill = timed_get(f"/knowledge/skills/{top['skill_id']}")
    report("知识库：技能点详情", skill["title"] == top["title"] and len(skill["content"]) > 100)
    qs = timed_get("/knowledge/questions", params={"book": "全国导游基础知识", "limit": 5})
    report("知识库：题库浏览", qs["total"] > 0 and qs["questions"][0]["options"])
except Exception as e:
    report("知识库浏览", False, str(e))

# 3. 用户状态（空）
try:
    state = timed_get(f"/users/{USER}/state")
    report("用户状态（初始）", state["stats"]["total_skills"] == 713 and state["mastery"] is not None,
           f"stats={state['stats']}")
except Exception as e:
    report("用户状态（初始）", False, str(e))

# 4. 创建画像 + 记忆
try:
    p = timed_post("/profiles", {
        "user_id": USER,
        "background": "我是旅游管理专业大二学生，目标考取导游资格证，希望一次通过",
        "target_role": "导游资格证",
        "current_level": "basic",
    })
    state = timed_get(f"/users/{USER}/state")
    report("创建画像 + 记忆沉淀", state["profile"] is not None and len(state["memories"]) >= 1,
           f"memories={[m['content'] for m in state['memories']]}")
except Exception as e:
    report("创建画像 + 记忆沉淀", False, str(e))

# 5. 真题测验 + 判分
try:
    quiz = timed_post("/training/random", {"knowledge_point_ids": [], "difficulty": "", "limit": 1})
    q = quiz["questions"][0]
    ok_resp = timed_post("/training/submissions", {"user_id": USER, "question_id": q["question_id"], "answer": q["answer"]})
    report("真题判分（正确）", ok_resp["correct"] is True)
    wrong = {"A": "B", "B": "C", "C": "D", "D": "A"}[q["answer"]]
    bad_resp = timed_post("/training/submissions", {"user_id": USER, "question_id": q["question_id"], "answer": wrong})
    report("真题判分（错误）", bad_resp["correct"] is False)
except Exception as e:
    report("真题测验 + 判分", False, str(e))

# 6. 真实对话：问候
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION, "content": "你好，我想开始备考导游证"})
    dt = time.time() - t0
    report("对话：问候", len(resp["content"]) > 0, f"{dt:.1f}s · {resp['content'][:50]}")
except Exception as e:
    report("对话：问候", False, str(e))

# 7. 真实对话：知识问答（应触发 search_knowledge）
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION, "content": "中国古典园林有哪些构景手法？请详细讲讲"})
    dt = time.time() - t0
    report("对话：知识问答(检索)", len(resp["content"]) > 20, f"{dt:.1f}s · {resp['content'][:60]}")
except Exception as e:
    report("对话：知识问答(检索)", False, str(e))

# 8. 真实对话：学习计划（generate_plan）
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION, "content": "帮我制定一个导游证备考学习计划"})
    dt = time.time() - t0
    report("对话：学习计划", len(resp["content"]) > 30, f"{dt:.1f}s · {resp['content'][:60]}")
except Exception as e:
    report("对话：学习计划", False, str(e))

# 9. 真实对话：生成讲义 + 六帽审查（长路径，异步执行）
try:
    t0 = time.time()
    resp = send_message({"user_id": USER, "session_id": SESSION,
                         "content": "请帮我生成一份《突发事件应急处置》的学习讲义，要涵盖应急处置制度、应急响应级别和处置流程"})
    dt = time.time() - t0
    ok = len(resp["content"]) > 50
    report("对话：生成讲义+六帽审查(异步)", ok, f"{dt:.1f}s · review={resp['review']} · {resp['content'][:60]}")
except Exception as e:
    report("对话：生成讲义+六帽审查(异步)", False, str(e))

# 10. 最终用户状态
try:
    state = timed_get(f"/users/{USER}/state")
    report("最终用户状态", state["stats"]["attempted_skills"] >= 1 and "weak_point_titles" in state,
           f"stats={state['stats']} weak={state['weak_point_titles'][:2]}")
except Exception as e:
    report("最终用户状态", False, str(e))


print("\n===== 汇总 =====")
for r in results:
    print(r)
print(f"\n通过 {passed} / {passed + failed}")
raise SystemExit(0 if failed == 0 else 1)
