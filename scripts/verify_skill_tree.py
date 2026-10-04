"""技能树 v2 + 沙盒一对一 真实验证（真实 API）：
  A. GET /skills/{user_id}/tree 结构：8 分支 32 节点
  B. activate_skill 记录与点亮（handler 直调）
  C. 真实训练答题提升掌握度 → 规则自动点亮（auto 来源）
  D. 沙盒一对一：违规场景游客回复不提及第三方（「其他游客/你去管管」）
用法：.venv/Scripts/python scripts/verify_skill_tree.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.services.sandbox import SandboxService
from brain_of_cloud.services.skill_tree import SkillTreeService
from brain_of_cloud.storage.sqlite import SQLiteStore

PASS = 0
FAIL = 0

THIRD_PARTY_WORDS = ["其他游客", "别的游客", "那位游客", "另一个游客", "旁边的", "你去管", "去劝阻", "有人乱", "有个人"]


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def main() -> int:
    print("=== 技能树 v2 + 沙盒一对一 真实验证 ===")
    tmp = tempfile.mkdtemp(prefix="boc_sk_")
    store = SQLiteStore(Path(tmp) / "sk.sqlite")
    store.initialize()
    plugin = TourGuidePlugin()
    llm = LLMClient()

    # ── A. 技能树接口结构 ──
    print("\n── A. 技能树结构 ──")
    svc = SkillTreeService(store)
    tree = svc.get_tree("u_sk", plugin=plugin)
    branches = tree["branches"]
    node_count = sum(len(b["nodes"]) for b in branches)
    check("A 9 分支 × 4 层 × 平行子节点（77 节点）",
          len(branches) == 9 and node_count == 77 and all(len({n["layer"] for n in b["nodes"]}) == 4 for b in branches),
          f"→ {len(branches)} 分支 / {node_count} 节点")
    check("A 节点字段完整", all({"id", "name", "ic", "layer", "d", "lit", "source", "reason",
                                 "mastery", "linked_count"} <= set(n.keys())
                               for b in branches for n in b["nodes"]), "")
    # 平行子节点示例：lang 第 1 层 3 个节点
    lang = next(b for b in branches if b["key"] == "lang")
    l1_group = [n["id"] for n in lang["nodes"] if n["layer"] == 1]
    check("A 平行子节点（lang 层1 = L1/L12/L13）", l1_group == ["L1", "L12", "L13"], f"→ {l1_group}")

    # ── B. activate_skill（管家主动点亮） ──
    print("\n── B. 管家主动点亮 ──")
    orch = Orchestrator(store=store, plugin=plugin, llm_client=llm)
    orch._user_id_ctx.set("u_sk")
    orch._session_id_ctx.set("s_sk")
    payload = json.loads(orch._handle_activate_skill("G1", "学员在园林构景讲解中表现出色，掌握了讲解入门"))
    check("B 点亮成功", payload.get("ok") is True, f"→ {payload}")
    tree2 = svc.get_tree("u_sk", plugin=plugin)
    g1 = next(n for b in tree2["branches"] for n in b["nodes"] if n["id"] == "G1")
    check("B 节点已点亮（concierge 来源）", g1["lit"] and g1["source"] == "concierge", f"→ {g1}")
    bad = json.loads(orch._handle_activate_skill("ZZ9", "无效"))
    check("B 非法节点被拒绝", bad.get("error") == "invalid_node_id", f"→ {bad}")

    # ── C. 真实训练答题 → 掌握度 → auto 点亮（独立用户，避免与 B 的管家点亮合并） ──
    print("\n── C. 训练答题提升掌握度 → 规则自动点亮 ──")
    orch2 = Orchestrator(store=store, plugin=plugin, llm_client=llm)
    orch2._user_id_ctx.set("u_auto")
    orch2._session_id_ctx.set("s_train")
    # 锁定一个主题并连续答对（真实判分，掌握度上升）
    orch2._handle_set_teaching_topic(["b01__skill_00098"])  # 借景（园林讲解类 → G1）
    q1 = json.loads(orch2._handle_quiz_user())
    if q1.get("question_id"):
        qid = q1["question_id"]
        try:
            idx = int(qid.split("_")[-1])
        except ValueError:
            idx = 0
        bank = json.loads(Path("data/master_question_bank.json").read_text(encoding="utf-8"))
        questions = bank["questions"]
        answer = questions[idx]["答案"] if 0 <= idx < len(questions) else "A"
        r = json.loads(orch2._handle_submit_answer(qid, answer))
        print(f"  答题判分：{r.get('correct')}（{qid}）")
        tree3 = svc.get_tree("u_auto", plugin=plugin)
        lit_nodes = [n for b in tree3["branches"] for n in b["nodes"] if n["lit"] and n["source"] == "auto"]
        check("C 掌握度规则自动点亮生效", len(lit_nodes) >= 1,
              f"→ auto 点亮 {[n['id'] for n in lit_nodes]}")
        if lit_nodes:
            print(f"  点亮理由：{lit_nodes[0]['reason']}")
    else:
        print(f"  出题失败：{q1}")
        check("C 训练链路可用", False, f"→ {q1}")

    # ── D. 沙盒一对一：违规场景不出现第三方 ──
    print("\n── D. 沙盒一对一（游客不指派处理第三者） ──")
    sb = SandboxService(llm_client=llm, store=store)
    session = sb.start_session(user_id="u_sk", template_id="t_guzhen_violation")
    sid = session["session_id"]
    print(f"  游客：{session['customer']['name']}（{session['customer']['nationality']}）")
    third_party_hits = []
    lines = [
        "先生您好，这里是文物保护区域，请您先移步护栏外。",
        "我理解您可能不知道规矩，这座基座有一千多年历史了。",
        "您看那边有个观景台，我陪您过去，顺便给您讲讲这座建筑的故事。",
        "烟抽完这边有专门的吸烟区，我领您过去。",
    ]
    for line in lines:
        r = sb.send_message(sid, line)
        hit = [w for w in THIRD_PARTY_WORDS if w in r["reply"]]
        if hit:
            third_party_hits.append((r["reply"][:50], hit))
        print(f"  轮[{r['stage']} 信任{r['trust']}] 游客：{r['reply'][:46]}")
        if r["scene_complete"]:
            break
    check("D 游客回复无第三方指派人", not third_party_hits, f"→ {third_party_hits}")
    check("D 信任/情绪状态随对话更新", "trust" in r and 0 <= r["trust"] <= 100, f"→ trust={r['trust']}")

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
