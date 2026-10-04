"""T8 真实验证：审查判定标准修正（评审反馈 #6）。
验证点：
  A. 讲解转化式材料（口语化 + 举例 + 与原文措辞完全不同、但无矛盾）→ 六帽审查必须放行（合格）
  B. 含明显虚假事实的材料（与知识库矛盾）→ 审查必须拦截（白帽指出矛盾 / 蓝帽需修改）
用法：.venv/Scripts/python scripts/verify_review_standard.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.domain.models import AgentId
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents.black_hat import BlackHatAgent
from brain_of_cloud.services.agents.blue_hat import BlueHatAgent
from brain_of_cloud.services.agents.white_hat import WhiteHatAgent

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
    print("=== T8 审查判定标准真实验证 ===")
    plugin = InboundGuidePlugin()
    llm = LLMClient()
    white = WhiteHatAgent(llm)
    black = BlackHatAgent(llm)
    blue = BlueHatAgent(llm)

    # ── 检索一个主题的证据（接站流程） ──
    evidence = plugin.search("机场接站流程 接机 导游", top_k=5)
    if not evidence:
        print("  [FAIL] 检索无证据，无法验证"); return 1
    print(f"  证据数: {len(evidence)}，首条来源: {evidence[0].source}")

    # ── A. 讲解转化式材料（同义重写 + 举例，无矛盾，措辞与原文完全不同） ──
    material_a = """接站服务速成要点
接团这件事，说穿了就是"接得到、对得上、安顿好"。
第一，接机前把该做的功课做足：航班号、抵达时间、人数、团号这些硬信息，出发前一晚再核对一遍，宁可早到半小时在到达口等着，也别让客人下了飞机找你。出发前最好再和领队确认一次有没有晚点，现在航班变动太频繁了。
第二，认人别认错。举牌要举得高、写得大，把客人名字和团号都写清楚。接团时先自报家门：我是谁、代表哪家旅行社、来接几号团，然后逐一点名确认，别嫌麻烦——你见过机场出口乱成一锅粥的样子吧，导游就是那根定海神针。
第三，见面后的第一印象决定整团的心情。主动帮客人提行李，尤其是女士和老人；问一句路上累不累；上车前把今天的行程简单交代两句，别一上来就推销自费项目。
最后提醒一个最常见的坑：只顾着对名单，忘了看行李票，结果客人行李丢了都不知道是谁的责任。接站结束后要当着客人的面清点人数和行李件数，再出发。""".strip()

    # ── B. 含虚假事实的材料（与知识库/常识矛盾） ──
    material_b = """接站时导游有权自行决定航班延误后的处理
根据行业惯例，航班延误超过两小时，导游可以不经任何确认，直接更改全团航班和酒店，费用由游客自理。
如果游客对更改不满，导游有权拒绝其随团继续行程。"""

    print("\n── A. 讲解转化材料（应放行） ──")
    start = time.time()
    white_a = white.run(material_a, evidence)
    black_a = black.run(material_a, evidence)
    blue_a = blue.coordinate(material_a, {AgentId.WHITE_HAT: white_a, AgentId.BLACK_HAT: black_a})
    print(f"  白帽: {white_a.content[:150]}")
    print(f"  黑帽: {black_a.content[:150]}")
    print(f"  蓝帽: {blue_a[:150]}")
    passed_a = "合格" in blue_a or ("通过" in white_a.content and "通过" in black_a.content)
    check("A 讲解转化材料被放行", passed_a, f"→ 蓝帽: {blue_a[:80]}")
    dedup_ok = "演绎" in white_a.content or "举例" in white_a.content or "原文" in white_a.content
    check("A 白帽识别了演绎/转化性质", dedup_ok, "→ 白帽未出现演绎/原文相关表述")
    print(f"  A 耗时 {time.time()-start:.1f}s")

    print("\n── B. 虚假材料（应拦截） ──")
    start = time.time()
    white_b = white.run(material_b, evidence)
    black_b = black.run(material_b, evidence)
    blue_b = blue.coordinate(material_b, {AgentId.WHITE_HAT: white_b, AgentId.BLACK_HAT: black_b})
    print(f"  白帽: {white_b.content[:150]}")
    print(f"  黑帽: {black_b.content[:150]}")
    print(f"  蓝帽: {blue_b[:150]}")
    blocked_b = ("矛盾" in white_b.content or "虚假" in white_b.content or "虚构" in white_b.content
                 or "不通过" in white_b.content or "需修改" in blue_b)
    check("B 虚假材料被拦截", blocked_b, f"→ 白帽: {white_b.content[:60]} | 蓝帽: {blue_b[:60]}")
    print(f"  B 耗时 {time.time()-start:.1f}s")

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
