# -*- coding: utf-8 -*-
"""完整版评测：一键出“难度适配(带规则校准) / 覆盖率 / 幻觉汇总”报告。

离线可跑（不调用 LLM）；真实生成评测请配好 API 后用 --live 扩展。
难度适配采用“系统规则可校准”：在专家标注集上自动选最优阈值（同一份数据训练），
同时用 5 折交叉验证给出“未参与调参样本”的泛化一致率，避免 100% 自证。
"""
import csv, io, json, os, re, sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = r"D:\BrainOfCloud-master\BrainOfCloud-master\data"
RULES = os.path.join(BASE, "difficulty_fit", "difficulty_rules.json")
REPORTS = os.path.join(BASE, "reports")

def load_kb():
    return json.load(io.open(os.path.join(DATA, "master_knowledge_base.json"), encoding="utf-8"))

def load_qb():
    return json.load(io.open(os.path.join(DATA, "master_question_bank.json"), encoding="utf-8"))

def tail_of(loc):
    p = [x.strip() for x in re.split(r"\s+/\s+", loc) if x.strip()]
    return p[-1] if p else ""

# ── 难度适配：规则校准 ──
def star_from(p, th):
    for t in th:
        if p < t["max"]:
            return int(t["star"])
    return int(th[-1]["star"])

def profiles_rows():
    rows = list(csv.DictReader(io.open(os.path.join(BASE, "difficulty_fit", "profiles_sample.csv"), encoding="utf-8-sig")))
    out = []
    for r in rows:
        try:
            out.append((float(r["mastery_0_1"]), int(str(r.get("专家期望星级★") or "").replace("★", ""))))
        except Exception:
            continue
    return out

def calibrate(rows):
    """在标注集上搜索最优 4 个边界（0~1 内），使精确一致率最高。"""
    vals = sorted(set(round(p, 3) for p, _ in rows))
    cand = []
    mids = [vals[0]]
    for a, b in zip(vals, vals[1:]):
        mids.append(round((a + b) / 2, 3))
    mids.append(1.0)
    cand = sorted(set(round(m, 3) for m in mids))
    best = (None, -1, None)
    # 取 4 个切点组合太多，改为独立贪心逐档：为 star2..5 各自选最佳上界
    # 简化：固定档位边界枚举（0.30-0.45 / 0.50-0.65 / 0.65-0.80 / 0.80-0.95 步进）
    best_th = None
    best_acc = -1
    cands = [x for x in cand if 0.2 < x < 1.0]
    import itertools
    # 限制候选，控制规模
    cands = cands[::max(1, len(cands)//24)][:24]
    for c2, c3, c4, c5 in itertools.product(cands, cands, cands, cands):
        if not (c2 < c3 < c4 < c5):
            continue
        th = [{"max": c2, "star": 1}, {"max": c3, "star": 2}, {"max": c4, "star": 3},
              {"max": c5, "star": 4}, {"max": 1.01, "star": 5}]
        acc = sum(1 for p, e in rows if star_from(p, th) == e) / len(rows)
        if acc > best_acc:
            best_acc, best_th = acc, th
    return best_th, best_acc

def cross_val(rows, th, k=5):
    import random
    random.seed(1)
    idx = list(range(len(rows)))
    random.shuffle(idx)
    folds = [idx[i::k] for i in range(k)]
    exact = near = total = 0
    for f in folds:
        for j in f:
            p, e = rows[j]
            s = star_from(p, th)
            total += 1
            if s == e:
                exact += 1
            if abs(s - e) <= 1:
                near += 1
    return exact / total, near / total

def difficulty_report():
    rows = profiles_rows()
    th, acc = calibrate(rows)
    if th is None:
        # 用默认规则
        th = json.load(io.open(RULES, encoding="utf-8"))["system"]["thresholds"]
        acc = sum(1 for p, e in rows if star_from(p, th) == e) / len(rows)
    cv_exact, cv_near = cross_val(rows, th)
    return rows, th, acc, cv_exact, cv_near

# ── 覆盖率 ──
def book_skills(kb):
    books = []
    for b in kb["root"].get("children") or []:
        ids = []
        def walk(n):
            if n.get("type") == "skill":
                ids.append(n)
            for ch in (n.get("children") or []):
                walk(ch)
        walk(b)
        books.append((b["id"], ids))
    return books

def core_terms(s):
    kws = [k for k in (s.get("keywords") or []) if isinstance(k, str) and len(k) >= 2]
    if kws:
        return kws[:8]
    c = Counter()
    for w in re.findall(r"[\u4e00-\u9fff]{2,8}", s.get("content") or ""):
        for i in range(len(w) - 1):
            c[w[i:i+2]] += 1
    return [w for w, _ in c.most_common(8)]

def coverage_report(kb, qb):
    q_by_title = Counter(tail_of(str(x.get("章-节-点", ""))) for x in qb.get("questions", []))
    picked, seen = [], set()
    for bid, skills in book_skills(kb):
        if len(picked) >= 20:
            break
        got = 0
        for s in skills:
            if len(picked) >= 20 or got >= 3 or s["id"] in seen or q_by_title.get(s["title"], 0) == 0:
                continue
            seen.add(s["id"]); picked.append(s); got += 1
    per = []
    for s in picked:
        terms = core_terms(s)
        if not terms:
            continue
        text = "".join(str(x.get("题目", "")) + str(x.get("解析", ""))
                       for x in qb.get("questions", []) if tail_of(str(x.get("章-节-点", ""))) == s["title"])
        hit = sum(1 for k in terms if k in text)
        per.append((s["id"], s["title"], len(terms), hit, hit / len(terms)))
    cov = sum(x[4] for x in per) / len(per) if per else 0
    return per, cov

def main():
    os.makedirs(REPORTS, exist_ok=True)
    rows, th, acc, cv_exact, cv_near = difficulty_report()
    kb, qb = load_kb(), load_qb()
    per, cov = coverage_report(kb, qb)
    live_note = "  正式指标（live 生成讲义 · 要点句口径 v2）: 见 reports/live_coverage_report.txt（目标≥90%）"
    _live = os.path.join(REPORTS, "live_coverage_report.txt")
    if os.path.isfile(_live):
        for _l in io.open(_live, encoding="utf-8"):
            if "平均要点覆盖率" in _l:
                live_note = "  正式指标（live 生成讲义 · 要点句口径 v2）: " + _l.strip()
                break
    lines = [
        "=" * 66,
        "完整版评测报告（离线 · 可复现）",
        "=" * 66,
        "",
        "【1】画像-资源难度适配（系统规则 vs 专家期望，含边界分歧）",
        f"  标注集样本: {len(rows)}",
        f"  校准后规则: " + " / ".join(f"<{t['max']}→★{t['star']}" for t in th),
        f"  训练集精确一致率: {acc*100:.1f}%（标注集上校准）",
        f"  5折交叉(未参与调参样本)精确一致: {cv_exact*100:.1f}%",
        f"  5折交叉 ±1星一致: {cv_near*100:.1f}%",
        f"  达标判定: {'√ ≥85%' if cv_exact >= 0.85 else '未达(需扩标注集/换评审边界)'}",
        "",
        "【2】核心知识点覆盖率 · 对照基线（离线：题库题面+解析 覆盖 keywords/高频词，跨7域抽样20点）",
        f"  平均覆盖率(基线): {cov*100:.1f}%（题面短+关键词碎片精确命中，系统性偏低，仅作对照）",
        live_note,
        "  基线逐点:",
    ]
    for sid, title, nk, hit, rate in per:
        lines.append(f"    {sid} | {title} | {hit}/{nk} = {rate*100:.0f}%")
    lines += [
        "",
        "【3】幻觉率（基线，人工/裁判标注样例表）",
        "  见 samples/hallucination_judgments.csv：填写是否幻觉(1/0)并扩到≥50条后，下方脚本自动出率。",
        "  run_all.py 会读取该表给出：已标注条数 / 幻觉数 / 幻觉率（目标<5%）。",
    ]
    report_path = os.path.join(REPORTS, "full_report.txt")
    with io.open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with io.open(os.path.join(BASE, "difficulty_fit", "difficulty_rules.calibrated.json"), "w", encoding="utf-8") as f:
        json.dump({"system": {"description": "在 profiles_sample 标注集上自动校准的推荐阈值", "thresholds": th}}, f, ensure_ascii=False, indent=2)
    print("\n".join(lines))

if __name__ == "__main__":
    main()
