# -*- coding: utf-8 -*-
"""为破碎技能点标题起准确名（b04 地区整段简介→官方地区名；两处 b01 泄漏标题）。
用法: python scripts/fix_skill_titles.py          # dry-run 预览
      python scripts/fix_skill_titles.py --apply   # 写入(master+题库 loc 同步)
"""
import io, sys, json, os, shutil, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(R, "data", "master_knowledge_base.json")
BANK = os.path.join(R, "data", "master_question_bank.json")

REGION = {
    "北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市",
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "海南": "海南省",
    "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省",
    "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区", "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
    "香港": "香港", "澳门": "澳门", "台湾": "台湾",
}
OVERRIDES = {
    "b01__skill_00007": "新中国成立以来大事记",
    "b01__skill_00059": "《滕王阁序》重点词句释义",
}
BASES = sorted(REGION, key=len, reverse=True)

def main():
    master = json.load(open(MASTER, encoding="utf-8"))
    changes = {}
    for s in master["skills"]:
        sid = s["id"]
        if sid in OVERRIDES:
            changes[sid] = OVERRIDES[sid]
            continue
        if sid.startswith("b04__") and len(s["title"]) > 12:
            t = s["title"].strip()
            for b in BASES:
                if t.startswith(b):
                    changes[sid] = REGION[b]
                    break
    print("待改名技能点:", len(changes))
    for sid, nt in list(changes.items())[:6]:
        old = next(x["title"] for x in master["skills"] if x["id"] == sid)
        print("   %s | %s -> %s" % (sid, old[:22], nt))
    if "--apply" not in sys.argv:
        print("dry-run：加 --apply 写入。")
        return

    for p in (MASTER, BANK):
        shutil.copy2(p, os.path.join(tempfile.gettempdir(), os.path.basename(p) + ".pre-titlefix.json"))

    old_title = {s["id"]: s["title"] for s in master["skills"]}
    rename_by_old = {old_title[sid]: new for sid, new in changes.items() if sid in old_title}
    by_id = {s["id"]: s for s in master["skills"]}

    def walk(node):
        if node.get("id") in changes:
            node["title"] = changes[node["id"]]
        for c in node.get("children") or []:
            walk(c)
    walk(master["root"])
    for sid, nt in changes.items():
        if sid in by_id:
            by_id[sid]["title"] = nt

    bank = json.load(open(BANK, encoding="utf-8"))
    upd = 0
    for q in bank["questions"]:
        parts = [p.strip() for p in str(q.get("章-节-点", "")).split(" / ")]
        if parts and parts[-1] in rename_by_old:
            parts[-1] = rename_by_old[parts[-1]]
            q["章-节-点"] = " / ".join(parts)
            upd += 1
    with open(MASTER, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False)
    with open(BANK, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False)
    print("写入完成；题库 loc 同步更新:", upd)

if __name__ == "__main__":
    main()