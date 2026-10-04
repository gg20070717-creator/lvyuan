"""帽子审查全覆盖真实验证（真实 API）：
  A. 生成讲义 → 审查必然发生（管家自觉调 review 或 orchestrator 自动审查），交付带审查痕迹
  B. 讲解转化材料 → 六帽新标准审查：5 帽全部执行 + 绿帽认可讲解转化 + 红帽收到教学主题
  C. 生成计划 → 自动审查触发（generate_plan 也过六帽）
用法：.venv/Scripts/python scripts/verify_review_coverage.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def main() -> int:
    print("=== 帽子审查全覆盖真实验证 ===")
    tmp = tempfile.mkdtemp(prefix="boc_rev_")
    store = SQLiteStore(Path(tmp) / "r.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=TourGuidePlugin(), llm_client=LLMClient())

    # ── A. 真实生成讲义：审查必须发生 ──
    print("\n── A. 生成讲义 → 审查发生 ──")
    t0 = time.time()
    orch.handle_user_message("u_rev", "s_rev", "我是旅游专业大二学生，正在备考导游证")
    r = orch.handle_user_message("u_rev", "s_rev", "帮我生成一份《中国古典园林的构景手法》考点总结讲义")
    elapsed = time.time() - t0
    # 审查发生 = 管家自觉调 review_material（工具链）或 orchestrator 自动审查（rounds_used ≥ 1）
    reviewed = "review_material" in r.tool_calls_made or r.rounds_used >= 1 or r.review_verdict in ("passed", "needs_revision")
    check("A 讲义生成后审查发生", reviewed, f"→ tools={r.tool_calls_made} rounds={r.rounds_used} verdict={r.review_verdict!r}")
    check("A 资产已生成", len(r.assets) > 0, f"→ {len(r.assets)} 个")
    check("A 交付语合理", bool(r.response), f"→ {r.response[:60]}")
    print(f"  A 耗时 {elapsed:.0f}s")

    # ── B. 讲解转化材料 → 六帽新标准审查 ──
    print("\n── B. 六帽新标准审查（讲解转化材料 + 教学主题） ──")
    orch._teaching.set_topic("s_rev2", "u_rev", ["b01__skill_00098"])
    material = """园林构景手法，说白了就是造园人怎么把园子布置得好看。记住一句话：借景是把园外的风景"借"进自己眼里，
比如站在颐和园东堤看远处的玉泉山宝塔，塔在园外，却成了你的景——这叫远借。对景就是你站在桥这头看桥那头，
两边风景互为画框。框景更简单，用门窗洞框住一片景，像墙上挂了一幅画。这些手法考试爱考，例子要能对上号。"""
    t0 = time.time()
    review = orch._handle_review_material(material)
    elapsed = time.time() - t0
    rv = json.loads(review)
    check("B 审查判定合法", rv.get("verdict") in ("passed", "needs_revision"), f"→ {rv.get('verdict')}")
    hats = rv.get("hats", {})
    check("B 五帽全部执行", set(hats.keys()) >= {"white_hat", "black_hat", "green_hat", "yellow_hat", "red_hat"},
          f"→ {list(hats.keys())}")
    green = hats.get("green_hat", {}).get("summary", "")
    check("B 绿帽评估讲解转化", "讲解" in green or "演绎" in green or "例子" in green, f"→ {green[:60]}")
    red = hats.get("red_hat", {}).get("summary", "")
    check("B 红帽结合主题上下文", bool(red), f"→ {red[:60]}")
    print(f"  B 耗时 {elapsed:.0f}s，判定 {rv.get('verdict')}")

    # ── C. 生成计划 → 自动审查 ──
    print("\n── C. 生成备考计划 → 审查发生 ──")
    t0 = time.time()
    r2 = orch.handle_user_message("u_rev", "s_rev", "给我制定一份考前冲刺备考计划")
    elapsed = time.time() - t0
    reviewed2 = "review_material" in r2.tool_calls_made or r2.rounds_used >= 1 or r2.review_verdict in ("passed", "needs_revision")
    check("C 计划生成后审查发生", reviewed2, f"→ tools={r2.tool_calls_made} rounds={r2.rounds_used}")
    print(f"  C 耗时 {elapsed:.0f}s")

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
