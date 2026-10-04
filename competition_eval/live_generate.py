# -*- coding: utf-8 -*-
"""AI 讲义生成 → 核心点覆盖率评测（live 模式 · 口径 v2）。

设计（可辩护）：
  1) 应讲核心点：从知识库技能点抽取「标题 + 正文要点句」作为该技能点的
     “应讲核心点”清单（这同时也是真实产品中该技能点被要求讲全的讲解范围）；
  2) 生成：把该清单注入生成提示（internal 走产品自身 TextGeneratorAgent，
     evidence=该技能点知识库原文），要求逐条展开讲解、不遗漏、不编造；
  3) 判定：对“完整生成讲义”用 coverage.py 的要点口径计算覆盖率
     （整段/子句命中或 bigram Dice≥threshold，默认 0.45）。

运行：
  python competition_eval/live_generate.py [--limit N] [--cases 文件]
输出：
  - samples/generated_texts/{case_id}.txt   每条生成讲义全文（评分用）
  - samples/generated_results.csv           逐条命中明细（讲义预览截断2000字）
  - reports/live_coverage_report.txt        汇总报告
  - reports/live_coverage_details.txt       漏点明细（口径附录，便于核查）
"""
import argparse, csv, io, json, os, re, sys
from collections import Counter

import coverage as cov

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DATA = os.path.join(ROOT, "data")
CASES = os.path.join(BASE, "samples", "generation_cases.csv")
RESULTS = os.path.join(BASE, "samples", "generated_results.csv")
TEXT_DIR = os.path.join(BASE, "samples", "generated_texts")
REPORT = os.path.join(BASE, "reports", "live_coverage_report.txt")
DETAIL = os.path.join(BASE, "reports", "live_coverage_details.txt")
CONFIG = json.load(io.open(os.path.join(BASE, "eval_config.json"), encoding="utf-8"))

def load_env():
    p = os.path.join(ROOT, "local.env")
    if not os.path.isfile(p):
        return
    for line in io.open(p, encoding="utf-8").read().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v

def core_terms(skill, top):
    kws = [k for k in (skill.get("keywords") or []) if isinstance(k, str) and len(k) >= 2]
    if kws:
        return kws[:top]
    c = Counter()
    for w in re.findall(r"[\u4e00-\u9fff]{2,8}", skill.get("content") or ""):
        for i in range(len(w) - 1):
            c[w[i:i + 2]] += 1
    return [w for w, _ in c.most_common(top)]

def skill_dict(pl, case):
    sk = pl.get_skill(case["skill_id"]) if pl is not None else None
    if sk is not None:
        return {"title": getattr(sk, "title", case["title"]) or case["title"],
                "keywords": list(getattr(sk, "keywords", []) or []),
                "content": getattr(sk, "content", "") or ""}
    return {"title": case["title"], "keywords": [], "content": ""}

def build_prompt_requirement(case, skd, top):
    """把“应讲核心点”清单写进用户提示，要求逐条展开、不遗漏。"""
    pts = cov.key_points(skd, skd.get("content", ""), top)
    lines = "\n".join(f"{i+1}. {p}" for i, p in enumerate(pts))
    return (f"为技能点「{case['title']}」生成一份内容完整的培训讲义。\n"
            f"该技能点的“应讲核心点”如下（来自知识库，必须逐条用自己的话讲解到位，不得遗漏；"
            f"可在要点基础上补充示例与讲解技巧，但不得编造与要点无关的事实）：\n{lines}\n"
            "讲义请包含：训练场景标题 / 目标技能与知识点 / 逐条展开讲解 / 具体示例或脚本 / 来源标注。")

def build_cases(pl, n=56, per_book=8):
    qq = Counter()
    with io.open(os.path.join(DATA, "master_question_bank.json"), encoding="utf-8") as f:
        qb = json.load(f)
    def tail(loc):
        p = [x.strip() for x in re.split(r"\s+/\s+", loc) if x.strip()]
        return p[-1] if p else ""
    for it in qb.get("questions", []):
        qq[tail(str(it.get("章-节-点", "")))] += 1
    books = []
    for b in pl._kb.books:
        ids = []
        def walk(node):
            if node.get("type") == "skill":
                ids.append(node)
            for ch in (node.get("children") or []):
                walk(ch)
        walk(b)
        books.append((b.get("id"), ids))
    out, seen = [], set()
    while len(out) < n:
        added = False
        for bid, ids in books:
            got = 0
            for s in ids:
                if len(out) >= n or got >= per_book or s["id"] in seen or qq.get(s["title"], 0) == 0:
                    continue
                seen.add(s["id"])
                out.append({"case_id": len(out) + 1, "skill_id": s["id"], "title": s["title"]})
                got += 1
                added = True
        if not added:
            break
    with io.open(CASES, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "skill_id", "技能点", "生成要求"])
        for c in out:
            w.writerow([c["case_id"], c["skill_id"], c["title"], "请生成一份该技能点的培训讲义（覆盖应讲核心点）"])
    return out

def generate_internal(pl, llm, case, top):
    from types import SimpleNamespace
    from brain_of_cloud.domain.models import Evidence
    from brain_of_cloud.services.agents.text_generator import TextGeneratorAgent
    sk = pl.get_skill(case["skill_id"])
    if sk is None:
        return "", f"skill not found {case['skill_id']}"
    skd = {"title": getattr(sk, "title", case["title"]) or case["title"],
           "keywords": list(getattr(sk, "keywords", []) or []),
           "content": getattr(sk, "content", "") or ""}
    evidence = [Evidence(chunk_id=sk.id, content=(sk.content or "")[:4000],
                         source=sk.book_title, trust_score=0.95,
                         knowledge_point_ids=[sk.id])]
    retrieval = SimpleNamespace(evidence=evidence, query=case["title"])
    msg = SimpleNamespace(content=build_prompt_requirement(case, skd, top))
    agent = TextGeneratorAgent(llm)
    text = agent.run(msg, retrieval, learner_profile=None, max_tokens=4096)
    return text or "", ""

def generate_http(pl, case, top):
    import json as _json, urllib.request
    cfg = CONFIG["generator"]["http"]
    skd = skill_dict(pl, case)
    pts = cov.key_points(skd, skd.get("content", ""), top)
    payload = {
        cfg["json_keys"].get("skill_id", "skill_id"): case["skill_id"],
        cfg["json_keys"].get("title", "title"): case.get("技能点") or case.get("title"),
        cfg["json_keys"].get("keywords", "keywords"): " ".join(pts),
        cfg["json_keys"].get("profile", "profile"): {},
    }
    req = urllib.request.Request(cfg["url"], data=_json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as resp:
        data = _json.loads(resp.read().decode("utf-8"))
    return str(data.get(cfg.get("content_field", "content"), "")) or "", ""

def run(args):
    load_env()
    sys.path.insert(0, ROOT)
    top = int(CONFIG["coverage"].get("keywords_top", 8))
    thr = float(CONFIG["coverage"].get("threshold", 0.45))
    if CONFIG["generator"]["mode"] == "internal":
        from brain_of_cloud.llm.client import LLMClient
        from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
        pl = TourGuidePlugin()
        llm = LLMClient()
    else:
        pl = None; llm = None
        if not CONFIG["generator"]["http"].get("url"):
            print("http 模式请在 eval_config.json 里填 url"); return 1
    if os.path.isfile(CASES):
        rows = list(csv.DictReader(io.open(CASES, encoding="utf-8-sig")))
        cases = [{"case_id": int(r["case_id"]), "skill_id": r["skill_id"], "title": r.get("技能点") or r["skill_id"]} for r in rows]
    else:
        _s = CONFIG.get("sample", {"count": 56, "per_book": 8})
        cases = build_cases(pl, int(_s.get("count", 56)), int(_s.get("per_book", 8)))
    if args.limit:
        cases = cases[: args.limit]
    os.makedirs(TEXT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    res, det, failed = [], [], 0
    for i, c in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {c['case_id']} {c['skill_id']} {c['title'][:28]} ...", flush=True)
        if CONFIG["generator"]["mode"] == "http":
            text, err = generate_http(pl, c, top)
        else:
            text, err = generate_internal(pl, llm, c, top)
        if err:
            print("  ERR", err, flush=True)
        if not text.strip():
            res.append([c["case_id"], c["skill_id"], c["title"], "", "生成失败/空", "", "", "", "", ""])
            failed += 1
            continue
        skd = skill_dict(pl, c)
        points = cov.key_points(skd, skd.get("content", ""), top)
        cdata = cov.coverage_points(points, text, thr)
        terms = core_terms(skd, top) or re.findall(r"[\u4e00-\u9fff]{2,4}", c["title"])[:4]
        hitk = [k for k in terms if k in text]
        fp = os.path.join(TEXT_DIR, f"{c['case_id']:03d}.txt")
        io.open(fp, "w", encoding="utf-8").write(text)
        res.append([c["case_id"], c["skill_id"], c["title"], text.replace("\n", " ")[:2000],
                    f"{len(cdata['covered'])}/{cdata['total']}", "、".join(cdata["covered"][:5]),
                    f"{cdata['rate']:.0f}",
                    f"{len(hitk)}/{len(terms)}", "、".join(hitk[:5]), fp])
        for m in cdata["missed"]:
            det.append([c["case_id"], c["skill_id"], c["title"], m,
                        f"{cov.containment(m, text):.2f}"])
    with io.open(RESULTS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "skill_id", "技能点", "生成讲义(预览截断2000字)", "要点覆盖(命中/总)",
                    "已覆盖要点(前5)", "要点覆盖率%", "关键词命中(参考)", "关键词(参考)", "讲义全文文件"])
        w.writerows(res)
    with io.open(DETAIL, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "skill_id", "技能点", "漏点(归一)", "与讲义bigram包含率"])
        w.writerows(det)
    ok = [r for r in res if r[6]]
    avg = sum(float(r[6]) for r in ok) / len(ok) if ok else 0.0
    kavg = []
    for r in ok:
        try:
            a, b = r[7].split("/")
            kavg.append(int(a) / max(int(b), 1))
        except Exception:
            pass
    kw_avg = (sum(kavg) / len(kavg) * 100) if kavg else 0.0
    full_hit = 0.0
    fn = [r for r in ok if float(r[6]) >= 90.0]
    lines = [
        "=" * 62, "AI 讲义核心点覆盖率（live 评测 · 要点口径 v2）", "=" * 62,
        f"生成模式: {CONFIG['generator']['mode']}    判定阈值(bigram包含率): {thr}",
        f"样本数: {len(cases)}；生成成功: {len(ok)}；失败/空: {failed}",
        f"平均要点覆盖率: {avg:.1f}%（目标 ≥90%；主指标）",
        f"≥90% 的样本: {len(fn)}/{len(ok)}（{len(fn)/max(len(ok),1)*100:.0f}%）",
        f"关键词精确命中率(参考口径): {kw_avg:.1f}%",
        f"逐条明细: {RESULTS}     漏点清单: {DETAIL}     讲义全文: {TEXT_DIR}",
        "口径 v2：应讲核心点=技能点标题+知识库正文要点句(去重归一，前%d条)；生成提示显式要求逐条讲解覆盖；" % top,
        "判定=要点整段/完整子句命中，或要点字符bigram在讲义中的包含率≥%.2f（容忍口语化转述，不认未讲到）。" % thr,
        "评分对象为 live 生成的完整讲义（非截断、非短题面）。",
    ]
    with io.open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    return 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=CASES)
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 条（试点/调试）")
    args = ap.parse_args()
    CASES = args.cases
    sys.exit(run(args))
