"""真实端到端验证：进阶教学闭环（真实题库 + 真实 LLM，不 mock）。

A. 管家讲解后是否主动提议做题（消息级，真实 LLM）
B. 用户同意 → 出选择题（type=choice + options）
C. 用户答选择题 → 判分
D. handler 层：主题选择题全做完 → essay_ready → 真实 LLM 出简答题 → 真实 LLM 判分
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from brain_of_cloud.llm.client import LLMClient  # noqa: E402
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin  # noqa: E402
from brain_of_cloud.services.orchestrator import Orchestrator  # noqa: E402
from brain_of_cloud.storage.sqlite import SQLiteStore  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name} {detail}")
    if not cond:
        FAILS.append(name)


tmp = tempfile.mkdtemp(prefix="boc_verify_essay_")
store = SQLiteStore(Path(tmp) / "v.sqlite")
store.initialize()
orch = Orchestrator(store=store, plugin=TourGuidePlugin(), llm_client=LLMClient())
orch._user_id_ctx.set("u_verify")
orch._session_id_ctx.set("s_verify")

# ── A. 讲解 → 管家主动提议做题 ──
r = orch.handle_user_message("u_verify", "s_verify", "给我讲讲一五计划的背景和影响")
print("[A] tools:", r.tool_calls_made)
print("[A] 回复(前120):", r.response[:120].replace("\n", " "))
proposal = any(k in r.response for k in ("做题", "考考", "检验", "来几道", "出几道", "练练"))
check("A 讲解后主动提议做题", proposal, f"含提议词={proposal}")

# ── B. 用户同意 → 出选择题 ──
r = orch.handle_user_message("u_verify", "s_verify", "讲得不错，出两道题检验一下")
teach = r.teaching or {}
lq = teach.get("last_quiz") or {}
print("[B] tools:", r.tool_calls_made)
print("[B] last_quiz:", json.dumps(lq, ensure_ascii=False)[:200])
check("B 出选择题 type=choice", lq.get("type") == "choice", f"type={lq.get('type')}")
check("B 带选项", len(lq.get("options") or []) >= 2, f"options={len(lq.get('options') or [])}")
check("B 有题目", bool(lq.get("prompt")), f"prompt={str(lq.get('prompt'))[:30]}")

# ── C. 用户答选择题（用真实答案） ──
qid = lq.get("question_id") or ""
q = orch._training.get_question(qid)
answer_letter = ""
if q and q.options:
    import re as _re
    m = _re.match(r"^([A-D])", q.answer.strip())
    answer_letter = m.group(1) if m else q.answer.strip()
r = orch.handle_user_message("u_verify", "s_verify", f"我选 {answer_letter}")
teach2 = r.teaching or {}
print("[C] tools:", r.tool_calls_made, "| 连对:", teach2.get("consecutive_correct"))
check("C 选择题判分", r.tool_calls_made and "submit_answer" in r.tool_calls_made,
      f"tools={r.tool_calls_made}")

# ── D. handler 层：全做完 → 进阶简答 ──
state = orch._teaching.get_or_create("s_verify", "u_verify")
kp_ids = list(state.get("topic_ids") or [])
print("[D] 主题:", kp_ids)
if kp_ids:
    # 1) 提交该主题全部选择题（done 满）
    all_q = orch._plugin.questions_filtered(knowledge_point_ids=kp_ids)
    choice_q = [qq for qq in all_q if qq.options]
    for qq in choice_q:
        try:
            orch._training.submit("u_verify", qq.question_id, qq.answer.strip().upper()[:1])
        except Exception:
            pass
    # 2) 模拟已全部出过题
    state = orch._teaching.get_or_create("s_verify", "u_verify")
    state["quiz_history"] = [qq.question_id for qq in choice_q]
    orch._teaching.save(state)
    # 3) quiz_user → essay_ready
    p = json.loads(orch._handle_quiz_user())
    check("D1 全做完返回 essay_ready", p.get("type") == "essay_ready",
          f"type={p.get('type')} progress={p.get('progress')}")
    # 4) 真实 LLM 出简答题
    p2 = json.loads(orch._handle_generate_essay_question(knowledge_point_ids=kp_ids))
    check("D2 简答题生成", p2.get("type") == "essay" and p2.get("question") and p2.get("rubric"),
          f"question={str(p2.get('question'))[:40]} rubric={str(p2.get('rubric'))[:40]}")
    print("[D2] 简答题:", p2.get("question"))
    print("[D2] rubric:", p2.get("rubric"))
    # 5) 真实 LLM 判分（像样的答案）
    essay_qid = p2.get("question_id")
    good_answer = "一五计划即第一个五年计划，1953到1957年，在苏联帮助下优先发展重工业，" \
                  "初步建立起独立的工业体系，为工业化奠定基础，也改善了人民生活。"
    p3 = json.loads(orch._handle_submit_answer(essay_qid, good_answer, "essay"))
    check("D3 简答判分 correct", p3.get("correct") is True,
          f"correct={p3.get('correct')} score={p3.get('score')} feedback={str(p3.get('feedback'))[:40]}")
    print("[D3] 判分 feedback:", p3.get("feedback"))
    # 6) 差的答案 → 低分
    p4 = json.loads(orch._handle_submit_answer(essay_qid, "不知道", "essay"))
    check("D4 差答案低分", p4.get("correct") is False and p4.get("score", 1) < 0.7,
          f"correct={p4.get('correct')} score={p4.get('score')}")
else:
    check("D 主题已锁定", False, "主题为空")

print()
if FAILS:
    print("RESULT: FAIL", FAILS)
    sys.exit(1)
print("RESULT: ALL PASS")
