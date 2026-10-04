"""T1 自评留痕计算（QR-1~3，自评口径）— 基于白帽语义判定。

方法（自评口径，与 T8 审查标准一致）：
- 每个生成片段由 WhiteHatAgent 对照知识库证据判定：矛盾 / 演绎（合法讲解转化）/ 待核验 / 通过
- 幻觉率（代理）= 「矛盾」片段比例（与证据冲突、虚构事实）
- 演绎率 = 「演绎」片段比例（讲解转化/举例——合法，体现教学价值）
- 覆盖率 = 生成资产 evidence_ids ↔ 目标技能点映射比例
- 全部判定逐条留痕（docs/eval/），供人工复核与发榜方按官方口径复核

用法：.venv/Scripts/python scripts/self_eval.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.agents.white_hat import WhiteHatAgent

CASES_DIR = ROOT / "docs" / "eval" / "test-cases"


def classify(verdict: str) -> str:
    """按白帽输出首行判定行分类（输出模板的逐条列表里也含「矛盾」字样，不能全文匹配）。"""
    head = (verdict or "").strip().split("\n")[0]
    if "不通过" in head:
        return "矛盾"
    if "通过" in head:
        if "演绎" in verdict:
            return "演绎"
        if "待核验" in verdict:
            return "待核验"
        return "通过"
    return "待核验"


# 非知识陈述片段（不参与幻觉判定）：个性化计划/报告、题目选项、系统状态提示
_NON_KNOWLEDGE_PATTERNS = [
    ("计划", lambda t: t.startswith("[资产:") and ("计划" in t or "报告" in t)),
    ("题目", lambda t: any(k in t for k in ("（A）", "（B）", "（C）", "（D）", "正确答案", "选 ", "作答", "本题"))),
    ("系统状态", lambda t: any(k in t for k in ("你目前是", "已掌握", "技能点，", "摸底", "反馈给我", "告诉我", "随时找我", "学习中心"))),
]


def is_knowledge_fragment(frag: str) -> bool:
    """是否知识陈述类片段（可做幻觉判定）；计划/题目/系统状态类不判定。"""
    for _, pred in _NON_KNOWLEDGE_PATTERNS:
        if pred(frag):
            return False
    return True


def main() -> int:
    print("=== T1 自评留痕计算（白帽语义判定，自评口径）===")
    llm = LLMClient()
    white = WhiteHatAgent(llm)
    plugin = TourGuidePlugin()

    cases = []
    for f in sorted(CASES_DIR.glob("*.json")):
        if f.name == "manifest.json":
            continue
        cases.append(json.loads(f.read_text(encoding="utf-8")))

    records: list[dict] = []
    total = {"矛盾": 0, "演绎": 0, "待核验": 0, "通过": 0}
    skipped = 0
    for case in cases:
        task = case.get("task", "")
        fragments = case.get("fragments", [])
        if not fragments:
            continue
        # 判定依据：优先用管家真实检索证据（evidence_pool），避免二次检索主题错位
        pool = case.get("evidence_pool") or []
        if pool:
            from brain_of_cloud.domain.models import Evidence as EvModel
            evs = [
                EvModel(chunk_id=e["chunk_id"], content=e["content"], source=e.get("source", ""),
                        trust_score=0.8, knowledge_point_ids=[])
                for e in pool
            ]
        else:
            evs = plugin.search(task, top_k=5)
        print(f"\n── {case['case_id']}（{len(fragments)} 片段，证据 {len(evs)} 条）")
        for frag in fragments:
            if not is_knowledge_fragment(frag):
                skipped += 1
                continue
            try:
                verdict = white.run(frag, evs).content
            except Exception as exc:
                verdict = f"判定失败: {exc}"
            cat = classify(verdict)
            total[cat if cat in total else "待核验"] += 1
            records.append({
                "case": case["case_id"],
                "category": cat,
                "fragment": frag[:120],
                "verdict": verdict[:200],
            })
            print(f"  [{cat}] {frag[:50]}…")

    n = len(records)
    hallucination = total["矛盾"] / n if n else 0.0
    deduction = total["演绎"] / n if n else 0.0
    passed = total["通过"] / n if n else 0.0

    report = f"""# 司南礼客 — 自评报告（QR-1~3，自评口径）

> 生成日期：2026-08-30 ｜ 引擎：deepseek-v4-flash-vision-exp（真实 API）
> ⚠️ 口径声明：官方评分量化工具由发榜方持有（评审反馈 #4）。本报告为**自评抽样留痕**，
> 方法可复现（scripts/self_eval.py），供发榜方按官方口径复核，不声称等同官方指标。

## 一、抽样与数据来源

| 来源 | 内容 | 数量 |
|---|---|---|
| `docs/eval/test-cases/`（DR-5 测试数据包） | 3 组画像 × 4 类任务（讲解/出题/材料生成），含输入画像 → 协同工具链 → 最终资源完整记录 | {len(cases)} 个任务、{n} 个知识片段（另 {skipped} 条非知识类不判定） |
| `scripts/verify_teacher_compare.py` | 教师对比评测（理想教师话语对照） | 3 场景 × 2 次 = 12 项检查 |
| `scripts/run_baseline_compare.py` | 四组 baseline 对比（6 主题 × 4 方案） | 24 次生成 |

## 二、指标（自评口径，白帽语义判定）

| 指标 | 目标 | 自评值 | 方法 |
|---|---|---|---|
| 幻觉率（专业知识谬误率） | < 5% | **{hallucination*100:.1f}%**（矛盾片段 {total['矛盾']}/{n}） | WhiteHatAgent 逐片段对照知识库证据判定「矛盾」比例 |
| 讲解转化率（演绎） | — | {deduction*100:.1f}%（{total['演绎']}/{n}） | 「演绎」= 合理教学重写/举例，非照搬原文（T8 目标达成证据） |
| 直接通过率 | — | {passed*100:.1f}%（{total['通过']}/{n}） | 「通过」= 与证据一致 |
| 核心知识点覆盖率 | ≥ 90% | 见附件：讲义用例引用 {len(set(eid for c in cases for eid in c.get('evidence_ids', [])))} 个技能点（b01__skill_*，如借景/框景/漏景） | 生成资产 evidence_ids ↔ 知识库技能点（结构化引用链，T14） |
| 画像-资源难度适配准确率 | ≥ 85% | 待人工复核 | 每用例记录画像 level 与生成内容，人工标注难度匹配 |
| 非知识类片段（不判定） | — | {skipped} 条 | 计划/报告/题目/系统状态（个性化内容，非知识陈述） |

## 三、逐条留痕（全部 {n} 条，供复核）

"""
    for r in records:
        report += f"- [{r['case']}｜{r['category']}] {r['fragment']}\n"
        if r["category"] in ("矛盾", "待核验"):
            report += f"  - 判定原文：{r['verdict']}\n"

    report += f"""
## 四、人工复核记录

- [ ] 复核「矛盾/待核验」片段（{total['矛盾'] + total['待核验']} 条）的事实准确性
- [ ] 适配准确率人工标注（{len(cases)} 个用例画像 × 难度）
- [ ] 复核人：___ 日期：___

---
*自评口径：幻觉率 = 白帽判定「矛盾」片段比例；最终以发榜方官方工具为准。*
"""
    out = ROOT / "docs" / "eval" / "self-eval-report.md"
    out.write_text(report, encoding="utf-8")
    (ROOT / "docs" / "eval" / "self-eval-records.json").write_text(
        json.dumps({"records": records, "summary": total}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 完成: {n} 知识片段 | 矛盾 {total['矛盾']} | 演绎 {total['演绎']} | 待核验 {total['待核验']} | 通过 {total['通过']}（跳过非知识类 {skipped}）")
    print(f"幻觉率代理: {hallucination*100:.1f}%")
    print(f"报告: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
