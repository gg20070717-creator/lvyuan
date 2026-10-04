"""重新分类已有自评留痕（classify bug 修复后免重跑 LLM）并重生成报告。

用法：.venv/Scripts/python scripts/reclassify_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.self_eval import classify, is_knowledge_fragment

RECORDS = ROOT / "docs" / "eval" / "self-eval-records.json"
REPORT = ROOT / "docs" / "eval" / "self-eval-report.md"


def main() -> int:
    data = json.loads(RECORDS.read_text(encoding="utf-8"))
    records = data["records"]
    total = {"矛盾": 0, "演绎": 0, "待核验": 0, "通过": 0}
    for r in records:
        cat = classify(r.get("verdict", ""))
        r["category"] = cat
        total[cat] = total.get(cat, 0) + 1
    n = len(records)
    hallucination = total["矛盾"] / n if n else 0.0
    deduction = total["演绎"] / n if n else 0.0
    passed = total["通过"] / n if n else 0.0

    cases_dir = ROOT / "docs" / "eval" / "test-cases"
    cases = [json.loads(f.read_text(encoding="utf-8"))
             for f in sorted(cases_dir.glob("*.json")) if f.name != "manifest.json"]
    evidence_skill = len(set(eid for c in cases for eid in c.get("evidence_ids", [])))
    skipped = sum(1 for c in cases for f in c.get("fragments", []) if not is_knowledge_fragment(f))

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
| 幻觉率（专业知识谬误率） | < 5% | **{hallucination*100:.1f}%**（矛盾片段 {total['矛盾']}/{n}） | WhiteHatAgent 逐片段对照知识库证据判定「不通过」比例 |
| 讲解转化率（演绎） | — | {deduction*100:.1f}%（{total['演绎']}/{n}） | 「演绎」= 合理教学重写/举例，非照搬原文（T8 目标达成证据） |
| 直接通过率 | — | {passed*100:.1f}%（{total['通过']}/{n}） | 「通过」= 与证据一致 |
| 核心知识点覆盖率 | ≥ 90% | 讲义用例引用 {evidence_skill} 个技能点（b01__skill_*，如借景/框景/漏景） | 生成资产 evidence_ids ↔ 知识库技能点（结构化引用链，T14） |
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
*自评口径：幻觉率 = 白帽判定「不通过（矛盾）」片段比例；最终以发榜方官方工具为准。*
"""
    REPORT.write_text(report, encoding="utf-8")
    RECORDS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"重新分类完成: {n} 片段 | 矛盾 {total['矛盾']} | 演绎 {total['演绎']} | 待核验 {total['待核验']} | 通过 {total['通过']}")
    print(f"幻觉率代理: {hallucination*100:.1f}%")
    print(f"报告: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
