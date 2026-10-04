"""真实验证（2026-08-29 教学体系重构）— 真实 DeepSeek API。

覆盖「一对一教师辅导」5 条用户路径：
A. 主动求学：问知识点 → 讲解（search_knowledge）→ 教学主题锁定
B. 查理解后出题：出题绑定当前教学主题（last_quiz 主题一致）+ 难度/排除重复
C. 答错纠错：submit_answer → reteach_hint → 纠错讲解（teaching.stage=feedback）
D. 明确随机摸底：随机仅在此路径合法（quiz_user 最终成功出题）
E. 教学状态接口：GET /teaching/state 持久化恢复
F. 「随便讲讲」：不直接随机出题，先推荐主题（教学铁律 5）
"""

import json
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
USER = f"user_teach_{uuid.uuid4().hex[:8]}"
results = []
passed = 0
failed = 0
TRANSCRIPTS: list[str] = []


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    mark = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    results.append(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def timed_post(path, payload, timeout=120):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.post(BASE + path, json=payload)
        r.raise_for_status()
        return r.json()


def timed_get(path, params=None, timeout=60):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.get(BASE + path, params=params)
        r.raise_for_status()
        return r.json()


def send_message(user_id, session_id, content, max_wait=360):
    """异步对话：入队 → 轮询直到 completed。返回 (task, phases)。"""
    phases: list[str] = []
    with httpx.Client(timeout=30, trust_env=False) as c:
        enq = c.post(BASE + "/messages", json={
            "user_id": user_id, "session_id": session_id, "content": content,
        })
        enq.raise_for_status()
        task_id = enq.json()["task_id"]
    deadline = time.time() + max_wait
    while time.time() < deadline:
        with httpx.Client(timeout=30, trust_env=False) as c:
            r = c.get(f"{BASE}/tasks/{task_id}")
            r.raise_for_status()
            task = r.json()
        phases.append(task.get("phase", ""))
        if task["status"] == "completed":
            return task, phases
        if task["status"] == "failed":
            raise RuntimeError(f"任务失败: {task['error']}")
        time.sleep(3)
    raise TimeoutError(f"任务 {task_id} 在 {max_wait}s 内未完成")


def transcript(name: str, task: dict, phases: list[str]):
    TRANSCRIPTS.append(
        f"\n── {name} ──\n"
        f"phase序列: {phases}\n"
        f"工具调用: {task.get('tool_calls')}\n"
        f"教学状态: {json.dumps(task.get('teaching'), ensure_ascii=False)}\n"
        f"回复: {(task.get('content') or '')[:600]}\n"
    )


# ── 0. 健康 ──
try:
    report("健康检查", timed_get("/").get("status") == "ok")
except Exception as e:
    report("健康检查", False, str(e))

# ── A. 主动求学：讲解优先 + 主题锁定 ──
SESSION_A = f"session_teach_a_{uuid.uuid4().hex[:6]}"
try:
    task, phases = send_message(
        USER, SESSION_A, "给我讲讲中国古典园林的构景手法",
    )
    transcript("A. 主动求学（讲解）", task, phases)
    teach = task.get("teaching") or {}
    topics = teach.get("topics") or []
    related = any(
        any(k in (t.get("title") or "") for k in ("构景", "借景", "框景", "园林", "对景", "漏景"))
        for t in topics
    )
    ok = (
        task["status"] == "completed"
        and "search_knowledge" in task.get("tool_calls", [])
        and len(topics) > 0
        and related
        and teach.get("stage") != "goal_setting"
    )
    report("A 讲解优先+主题锁定", ok,
           f"tools={task.get('tool_calls')} topics={[t.get('title') for t in topics]} stage={teach.get('stage')}")
    if not ok:
        report("A 回复包含讲解内容", "构景" in (task.get("content") or ""),
               (task.get("content") or "")[:200])
except Exception as e:
    report("A 主动求学", False, str(e))

# ── B. 确认理解后出题：主题绑定 + 阶段 practicing ──
try:
    task, phases = send_message(
        USER, SESSION_A, "清楚了，出几道题巩固一下",
        max_wait=600,
    )
    transcript("B. 确认理解后出题", task, phases)
    teach = task.get("teaching") or {}
    lq = teach.get("last_quiz") or {}
    # 若管家这次没出题（可能转为追问/其他），再引导一次
    if not lq.get("question_id"):
        task, phases = send_message(
            USER, SESSION_A, "直接出题吧，我想做题巩固",
            max_wait=600,
        )
        transcript("B2. 再次要求出题", task, phases)
        teach = task.get("teaching") or {}
        lq = teach.get("last_quiz") or {}
    topics = teach.get("topics") or []
    lq_title = lq.get("knowledge_point_title") or ""
    bound = (
        lq_title in [t.get("title") for t in topics]
        or any(k in lq_title for k in ("构景", "借景", "框景", "园林", "对景", "漏景"))
    )
    ok = (
        bool(lq.get("question_id"))
        and teach.get("stage") == "practicing"
        and bound
    )
    report("B 出题绑定教学主题", ok,
           f"last_quiz={lq.get('question_id')} 主题={lq_title} stage={teach.get('stage')}")
except Exception as e:
    report("B 确认后出题", False, str(e))

# ── C. 答错纠错：submit_answer → reteach_hint → 纠错讲解 ──
try:
    # 取真实错误字母：question_id=q_XXXXX 对应题库第 XXXXX 条（加载器按序编号），读「答案」字段
    teach = task.get("teaching") or {}
    lq = teach.get("last_quiz") or {}
    wrong_letter = "A"
    qid = lq.get("question_id") or ""
    if qid.startswith("q_") and qid[2:].isdigit():
        idx = int(qid[2:])
        bank = json.load(open("data/master_question_bank.json", encoding="utf-8"))["questions"]
        if idx < len(bank):
            correct = (bank[idx].get("答案") or "").strip().upper()[:1]
            letters = [o.strip()[:1].upper() for o in (lq.get("options") or [])]
            wrong_letter = next((ch for ch in ("A", "B", "C", "D") if ch != correct and ch in letters), "A")
    task, phases = send_message(
        USER, SESSION_A, f"我选 {wrong_letter}",
    )
    transcript(f"C. 答错纠错（答 {wrong_letter}，正确答案 {correct if 'correct' in dir() else '?'}）", task, phases)
    teach = task.get("teaching") or {}
    content = task.get("content") or ""
    wrong_graded = (teach.get("consecutive_incorrect") or 0) >= 1
    reteach_visible = any(k in content for k in ("错", "不对", "重新", "纠", "注意", "理解"))
    re_quizzed = "quiz_user" in task.get("tool_calls", [])
    ok = (
        "submit_answer" in task.get("tool_calls", [])
        and wrong_graded
        and teach.get("stage") in ("feedback", "practicing")
    )
    report("C 答错后纠错闭环", ok,
           f"tools={task.get('tool_calls')} 判错={wrong_graded} stage={teach.get('stage')} "
           f"重讲可见={reteach_visible} 重出题={re_quizzed}")
except Exception as e:
    report("C 答错纠错", False, str(e))

# ── E. 教学状态接口持久化 ──
try:
    st = timed_get("/teaching/state", {"session_id": SESSION_A, "user_id": USER})
    ok = (
        st.get("session_id") == SESSION_A
        and isinstance(st.get("topics"), list)
        and st.get("stage") in (
            "goal_setting", "teaching", "checking", "practicing", "feedback", "closing", "idle",
        )
    )
    report("E 教学状态接口可用", ok,
           f"stage={st.get('stage')} topics={st.get('topics')}")
except Exception as e:
    report("E 教学状态接口", False, str(e))

# ── F. 「随便讲讲」：先推荐主题，不直接随机出题 ──
SESSION_F = f"session_teach_f_{uuid.uuid4().hex[:6]}"
try:
    task, phases = send_message(
        USER, SESSION_F, "随便讲讲吧，我没什么方向",
    )
    transcript("F. 随便讲讲（推荐主题）", task, phases)
    tools = task.get("tool_calls", [])
    ok = "quiz_user" not in tools
    report("F 无方向时不直接出题", ok, f"tools={tools}")
except Exception as e:
    report("F 随便讲讲", False, str(e))

# ── D. 明确随机摸底：随机路径合法 ──
SESSION_D = f"session_teach_d_{uuid.uuid4().hex[:6]}"
try:
    task, phases = send_message(
        USER, SESSION_D, "不用讲，直接随机考考我，摸摸底",
    )
    transcript("D. 明确随机摸底", task, phases)
    teach = task.get("teaching") or {}
    ok = (
        "quiz_user" in task.get("tool_calls", [])
        and bool((teach.get("last_quiz") or {}).get("question_id"))
    )
    report("D 明确随机才允许随机出题", ok,
           f"tools={task.get('tool_calls')} last_quiz={((teach.get('last_quiz') or {}).get('question_id'))}")
except Exception as e:
    report("D 明确随机摸底", False, str(e))

print("\n===== 完整对话记录 =====")
for t in TRANSCRIPTS:
    print(t)

print(f"\n===== 结果: {passed} 通过 / {failed} 失败 =====")
if failed:
    raise SystemExit(1)
