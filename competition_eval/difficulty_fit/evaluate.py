# -*- coding: utf-8 -*-
"""难度适配评测（题库推荐 vs 专家期望）——离线、可复现、无 LLM。

用法：
  python evaluate.py profiles_sample.csv
  python evaluate.py profiles_template.csv   # 填好“专家期望星级★”后使用
"""
import csv, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(io.open(os.path.join(HERE, "difficulty_rules.json"), encoding="utf-8"))
TH = RULES["system"]["thresholds"]  # [{"max": .., "star": ..}, ...]

def system_star(mastery: float) -> int:
    for t in TH:
        if mastery < t["max"]:
            return int(t["star"])
    return int(TH[-1]["star"])

def main(path: str) -> None:
    with io.open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    exact = 0
    near = 0
    total = 0
    mismatches = []
    boundary_exact = 0
    boundary_total = 0
    bounds = sorted(t["max"] for t in TH)
    for r in rows:
        try:
            p = float(r.get("mastery_0_1", "").strip())
            exp_raw = (r.get("专家期望星级★") or "").strip().replace("★", "")
            if exp_raw == "":
                continue  # 未填真值，跳过
            exp = int(exp_raw)
        except (ValueError, TypeError):
            continue
        sys_s = system_star(p)
        total += 1
        if sys_s == exp:
            exact += 1
        if abs(sys_s - exp) <= 1:
            near += 1
        else:
            mismatches.append((r["case_id"], r["身份"], p, sys_s, exp, r.get("备注", "")))
        # 边界样本：掌握度落在任一切换点 ±0.07 内
        if any(abs(p - b) < 0.07 for b in bounds):
            boundary_total += 1
            if sys_s == exp:
                boundary_exact += 1

    print("=" * 60)
    print("难度适配评测报告")
    print("=" * 60)
    print(f"有效样本(已填专家期望): {total}")
    if total == 0:
        print("未填写任何‘专家期望星级★’，请先人工标注后再运行。")
        return
    print(f"精确一致(系统==专家)   : {exact}/{total} = {exact/total*100:.1f}%")
    print(f"±1星宽松一致           : {near}/{total} = {near/total*100:.1f}%")
    if boundary_total:
        print(f"边界样本精确一致        : {boundary_exact}/{boundary_total} = {boundary_exact/boundary_total*100:.1f}%")
    print("-" * 60)
    if mismatches:
        print("不一致清单（系统推荐 vs 专家期望）：")
        for cid, ident, p, s, e, note in mismatches:
            print(f"  case {cid} | {ident} | mastery={p} | 系统★{s} vs 专家★{e} | {note}")
    else:
        print("无不一致——请警惕‘专家=系统规则镜像’导致的虚高 100%。")
    print("=" * 60)
    print("口径提醒：本指标不是系统自证；专家期望应由不了解本系统规则的评审按 rubric 填写。")
    print("若精确一致率≈100%，多半是期望规则与系统规则同源，需补充边界样本或更换评审。")

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "profiles_sample.csv")
    main(p)
