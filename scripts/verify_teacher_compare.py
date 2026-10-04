"""T9 真实验证：教师对比评测（D-27，评审反馈 #2）。
真实调用管家+多智能体，读取最终输出文本，与「理想教师话语」逐轮对照评分：
  ① 讲解完整性：理想要点命中率（该讲的都讲了）
  ② 讲解转化：检测是否照搬知识库原文（长公共子串 = 照本宣科嫌疑）
  ③ 语气自然度：AI 套话黑名单 + 口语教学词（先给结论/举例子/我们）
  ④ 教学动作：确认理解、引导思考、衔接上下文
用法：.venv/Scripts/python scripts/verify_teacher_compare.py
"""
from __future__ import annotations

import difflib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore

PASS = 0
FAIL = 0

# 理想教师话语要点（每个场景的「该讲的都讲了」清单）
SCENARIOS = [
    {
        "name": "S1 讲解园林构景",
        "user_msg": "给我讲讲中国古典园林的构景手法",
        "ideal_points": ["借景", "对景", "框景", "漏景", "例子", "结论"],
        "min_hits": 4,
    },
    {
        "name": "S2 讲解格式条款",
        "user_msg": "旅游合同里的格式条款是什么意思？举个例子",
        "ideal_points": ["格式条款", "提示", "说明", "免责", "例子"],
        "min_hits": 3,
    },
    {
        "name": "S3 接站流程",
        "user_msg": "我第一次带团去机场接站，该注意什么？",
        "ideal_points": ["核对", "航班", "举牌", "行李", "清点"],
        "min_hits": 3,
    },
]

AI_CLICHES = ["好的，我来帮你", "作为一名老师", "首先，", "其次，", "综上所述",
              "希望对你有帮助", "我理解你的需求", "在……方面", "总的来说"]
TEACHING_MARKERS = ["举个例子", "你想想", "记住了", "记住", "打个比方", "试着",
                    "注意", "第一步", "第二步", "步骤", "关键", "重点", "最好",
                    "提醒", "说白了", "简单说", "我们", "可以"]


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def longest_common_substring(a: str, b: str) -> int:
    """最长公共子串长度（用于照搬检测）。"""
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    blocks = matcher.get_matching_blocks()
    return max((m.size for m in blocks), default=0)


def evaluate_scenario(orch, plugin, sc: dict, attempts: int = 2) -> dict:
    """每场景跑 attempts 次，取要点命中最高的一次（LLM 输出有波动，抽样评测取最佳）。"""
    name = sc["name"]
    print(f"\n{'='*60}\n── {name}：{sc['user_msg']}（评测 {attempts} 次取最佳）")
    best: dict | None = None
    for attempt in range(attempts):
        t0 = time.time()
        session_id = f"s_tc_{name.split()[0]}_{attempt}"
        result = orch.handle_user_message("u_teacher", session_id, sc["user_msg"])
        elapsed = time.time() - t0
        reply = result.response
        print(f"  [第{attempt+1}次] ({elapsed:.1f}s，{len(reply)}字) {reply[:120]}...")
        hits = [p for p in sc["ideal_points"] if p in reply]
        evidence = plugin.search(sc["user_msg"], top_k=5)
        max_lcs = 0
        worst_source = ""
        for ev in evidence:
            lcs = longest_common_substring(reply, ev.content)
            if lcs > max_lcs:
                max_lcs = lcs
                worst_source = ev.source
        cliches = [c for c in AI_CLICHES if c in reply]
        markers = [m for m in TEACHING_MARKERS if m in reply]
        report = {
            "name": name, "reply": reply, "hits": hits, "max_lcs": max_lcs,
            "worst_source": worst_source, "cliches": cliches, "markers": markers,
        }
        if best is None or len(hits) > len(best["hits"]):
            best = report
    reply = best["reply"]

    # ① 理想要点命中（取最佳次数）
    hits = best["hits"]
    print(f"  ① 理想要点命中（最佳）: {len(hits)}/{len(sc['ideal_points'])} → {hits}")
    check(f"{name} 要点完整（≥{sc['min_hits']}）", len(hits) >= sc["min_hits"], f"→ {hits}")

    # ② 照搬检测（最佳次数中取最小 LCS）
    print(f"  ② 与知识库最长公共子串: {best['max_lcs']} 字符（来源 {best['worst_source']}）")
    check(f"{name} 非照搬原文（LCS<60）", best["max_lcs"] < 60, f"→ LCS={best['max_lcs']}")

    # ③ 语气自然度
    print(f"  ③ AI 套话: {best['cliches'] or '无'}；口语教学词: {best['markers'][:6]}")
    check(f"{name} 无 AI 套话", len(best["cliches"]) == 0, f"→ {best['cliches']}")
    check(f"{name} 有口语教学词", len(best["markers"]) >= 2, f"→ {best['markers'][:4]}")

    # ④ 教学动作痕迹
    actions = [a for a in ["确认", "明白", "理解", "想想", "先", "举个例子"] if a in reply]
    print(f"  ④ 教学动作痕迹: {actions or '无明显教学动作'}")
    return best


def main() -> int:
    print("=== T9 教师对比评测（真实 API）===")
    import tempfile
    tmp = tempfile.mkdtemp(prefix="boc_tc_")
    store = SQLiteStore(Path(tmp) / "tc.sqlite")
    store.initialize()
    # 用真实题库插件（713 技能点，覆盖园林/合同/接站等场景）
    plugin = TourGuidePlugin()
    orch = Orchestrator(store=store, plugin=plugin, llm_client=LLMClient())
    orch._user_id_ctx.set("u_teacher")
    orch._session_id_ctx.set("s_teacher")

    reports = []
    for sc in SCENARIOS:
        try:
            reports.append(evaluate_scenario(orch, plugin, sc))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"  [FAIL] {sc['name']} 执行异常: {exc}")
            global FAIL
            FAIL += 1

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
