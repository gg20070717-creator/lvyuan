# -*- coding: utf-8 -*-
"""赛题三项指标评测：一键跑全部，输出 reports/*.txt（离线、基于真实知识库/题库、可复现）。"""
import csv, io, json, os, random, re
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = r"D:\BrainOfCloud-master\BrainOfCloud-master\data"
REPORTS = os.path.join(BASE, "reports")
SAMPLES = os.path.join(BASE, "samples")
os.makedirs(REPORTS, exist_ok=True)
os.makedirs(SAMPLES, exist_ok=True)

def load_data():
    kb = json.load(io.open(os.path.join(DATA, "master_knowledge_base.json"), encoding="utf-8"))
    qb = json.load(io.open(os.path.join(DATA, "master_question_bank.json"), encoding="utf-8"))
    return kb, qb

def tail_of(loc):
    parts = [p.strip() for p in re.split(r"\s+/\s+", loc) if p.strip()]
    return parts[-1] if parts else ""

def book_skills(root):
    """按知识树逐书收集技能点（含 keywords/content）。"""
    books = []
    for book in root.get("children") or []:
        ids = []
        def walk(n):
            if n.get("type") == "skill":
                ids.append(n)
            for ch in (n.get("children") or []):
                walk(ch)
        walk(book)
        books.append((book.get("id"), book.get("title"), ids))
    return books

def core_terms(skill, top_n=8):
    """应讲核心点：优先用知识库 keywords；缺失则用正文高频词兜底。"""
    kws = [k for k in (skill.get("keywords") or []) if isinstance(k, str) and len(k) >= 2]
    if kws:
        return kws[:top_n]
    text = skill.get("content") or ""
    grams = Counter()
    for s in re.findall(r"[\u4e00-\u9fff]{2,8}", text):
        for i in range(len(s) - 1):
            grams[s[i:i+2]] += 1
    return [w for w, _ in grams.most_common(top_n) if w]

def pick_samples(kb, qb, cap=12, per_book=2):
    """跨书轮转抽样：每书至多 per_book 个，覆盖多个知识域。"""
    q_titles = Counter(tail_of(str(it.get("章-节-点", ""))) for it in qb.get("questions", []))
    books = []
    for bid, btitle, skills in book_skills(kb["root"]):
        pool = [dict(s) for s in skills if q_titles.get(s["title"], 0) > 0]
        books.append((bid, btitle, pool))
    out, seen = [], set()
    # 轮转直到 cap 或没有书还能取
    while len(out) < cap:
        added = False
        for bid, btitle, pool in books:
            got = 0
            for s in pool:
                if len(out) >= cap or got >= per_book:
                    break
                if s["id"] in seen:
                    continue
                seen.add(s["id"]); s = dict(s); s["_book"] = btitle
                out.append(s); got += 1; added = True
        if not added:
            break
    return out

def write_report(name, lines):
    with io.open(os.path.join(REPORTS, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def metric_hallucination(kb, qb, target=60):
    """抽样“题目解析 vs 知识库正文”待判表：跨7书均衡、种子固定可复现；旧标注按(技能点+题目)合并保留，不覆盖。"""
    q_by_title = defaultdict(list)
    for it in qb.get("questions", []):
        q_by_title[tail_of(str(it.get("章-节-点", "")))].append(it)
    rng = random.Random(20260905)
    def skills_of(node):
        out = []
        def w(n):
            if n.get("type") == "skill":
                out.append(n)
            for ch in (n.get("children") or []):
                w(ch)
        w(node)
        return out
    pools = []
    for book in (kb.get("root") or {}).get("children") or []:
        sk = [s for s in skills_of(book) if q_by_title.get(s.get("title", ""))]
        rng.shuffle(sk)
        pools.append((book.get("id"), book.get("title"), sk))
    sample_path = os.path.join(SAMPLES, "hallucination_judgments.csv")
    old = {}
    if os.path.exists(sample_path):
        try:
            for r in csv.DictReader(io.open(sample_path, encoding="utf-8-sig")):
                v = str(r.get("是否幻觉(1/0)") or "").strip()
                if v in ("0", "1"):
                    old[(r.get("skill_id"), str(r.get("题目") or ""))] = (v, str(r.get("判错理由") or "").strip())
        except Exception:
            old = {}
    idxs = [0] * len(pools)
    used = set()
    rows, case = [], 0
    while len(rows) < target:
        added = False
        for pi, (bid, btitle, sk) in enumerate(pools):
            if len(rows) >= target:
                break
            while idxs[pi] < len(sk):
                s = sk[idxs[pi]]; idxs[pi] += 1
                cand = [it for it in q_by_title.get(s.get("title", ""), [])
                        if (s.get("id"), str(it.get("题目", ""))) not in used
                        and str(it.get("解析") or "").strip()]
                if not cand:
                    continue
                it = rng.choice(cand)
                used.add((s.get("id"), str(it.get("题目", ""))))
                case += 1
                key = (s.get("id"), str(it.get("题目", "")))
                verdict, reason = old.get(key, ("", ""))
                ref = (s.get("content") or "").replace("\n", " ")[:220]
                rows.append([case, s.get("id"), s.get("title"),
                             str(it.get("题目", ""))[:140],
                             str(it.get("解析", ""))[:180], ref, verdict, reason])
                added = True
                break
        if not added:
            break
    with io.open(sample_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "skill_id", "技能点", "题目", "解析(待核文本)", "参考来源(知识库)", "是否幻觉(1/0)", "判错理由"])
        w.writerows(rows)
    judged = [r for r in rows if str(r[6]).strip() in ("0", "1")]
    wrong = sum(1 for r in judged if str(r[6]).strip() == "1")
    rate = wrong / len(judged) if judged else 0.0
    return [
        "=" * 60,
        "指标1 · 幻觉率（基线口径）",
        "=" * 60,
        "方法：抽样技能点题目“解析”与知识库正文，由独立裁判判定是否与参考冲突(幻觉)。",
        f"抽样口径：跨 {len(pools)} 本书轮转、{len(rows)} 个技能点各抽1题（种子固定可复现）；旧标注按技能点+题目合并保留。",
        "",
        f"样例文件: {sample_path}",
        f"生成待判条数: {len(rows)}",
        f"已标注条数: {len(judged)}（目标 ≥50）",
        f"判定为幻觉条数: {wrong}",
        f"幻觉率: {rate*100:.1f}%（赛题目标 <5%）",
    ]

def metric_difficulty_fit():
    sample = os.path.join(BASE, "difficulty_fit", "profiles_sample.csv")
    rules = json.load(io.open(os.path.join(BASE, "difficulty_fit", "difficulty_rules.json"), encoding="utf-8"))
    th = rules["system"]["thresholds"]
    def star(p):
        for t in th:
            if p < t["max"]:
                return int(t["star"])
        return int(th[-1]["star"])
    rows = list(csv.DictReader(io.open(sample, encoding="utf-8-sig")))
    exact = near = total = 0
    for r in rows:
        try:
            p = float(r["mastery_0_1"]); e = int(str(r.get("专家期望星级★") or "").replace("★", ""))
        except Exception:
            continue
        total += 1
        s = star(p)
        if s == e:
            exact += 1
        if abs(s - e) <= 1:
            near += 1
    ea = exact / total * 100 if total else 0
    na = near / total * 100 if total else 0
    return [
        "=" * 60,
        "指标2 · 画像-资源难度适配准确率",
        "=" * 60,
        "方法：系统掌握度规则给推荐星级，与外部专家 rubric 预标期望比对（专家不读系统规则）。",
        f"样例文件: {sample}（20 组画像，含边界与 4 条 ±1 分歧）",
        f"有效样本: {total}",
        f"精确一致率: {exact}/{total} = {ea:.1f}%（目标 ≥85%；扩到 ≥50 组且保持独立标注后作为正式结论）",
        f"±1 星宽松一致率: {near}/{total} = {na:.1f}%",
    ]

def metric_coverage(skills, qb):
    q_by_title = defaultdict(list)
    for it in qb.get("questions", []):
        q_by_title[tail_of(str(it.get("章-节-点", "")))].append(it)
    per = []
    for s in skills:
        terms = core_terms(s)
        if not terms:
            continue
        text = "".join(str(it.get("题目", "")) + str(it.get("解析", "")) for it in q_by_title.get(s["title"], []))
        hit = sum(1 for k in terms if k in text)
        per.append((s["id"], s["title"], len(terms), hit, hit / len(terms)))
    cov = sum(p[4] for p in per) / len(per) if per else 0
    lines = [
        "=" * 60,
        "指标3 · 核心知识点覆盖率",
        "=" * 60,
        "方法：知识库 keywords（缺失时用正文高频词）作为“应讲核心点”；覆盖 = 题面+解析中出现核心点的比例。",
        f"抽样技能点: {len(per)}",
        "逐点明细:",
    ]
    for sid, title, nk, hit, rate in per:
        lines.append(f"  {sid} | {title} | 核心点命中 {hit}/{nk} = {rate*100:.0f}%")
    lines.append(f"平均核心知识点覆盖率: {cov*100:.1f}%（目标 ≥90%）")
    return lines

def main():
    kb, qb = load_data()
    skills = pick_samples(kb, qb, cap=20, per_book=3)
    r1 = metric_hallucination(kb, qb, target=60)
    r2 = metric_difficulty_fit()
    r3 = metric_coverage(skills, qb)
    write_report("01_hallucination.txt", r1)
    write_report("02_difficulty_fit.txt", r2)
    write_report("03_coverage.txt", r3)
    for rs in (r1, r2, r3):
        print("\n" + "\n".join(rs))

if __name__ == "__main__":
    main()
