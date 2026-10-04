# -*- coding: utf-8 -*-
"""生成跨文化知识库骨架（两个并列库，四层固定 + 第五层 AI 知识点）。

结构（与现有 master_knowledge_base.json 同构，loader/catalog 无需改动）：

1) data/culture_customs_kb.json
   master(总库) → book(文化习惯知识) → part(20 国家) → chapter(3 维度) → section(主题) → skill(AI)

2) data/cultural_bridge_kb.json
   master(总库) → book(文化桥) → part(20 个「中×文化桥」) → chapter(6 维度) → section(主题) → skill(AI)

用法:  python scripts/build_cross_culture_kb.py
输出:  data/culture_customs_kb.json, data/cultural_bridge_kb.json
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# ---------------------------------------------------------------------------
# 20 国基础信息（ISO 小写两字码 / 中文名 / 国家速览 content）
# ---------------------------------------------------------------------------
COUNTRIES = [
    ("us", "美国", "首都华盛顿哥伦比亚特区 / 官方语言英语 / 主要宗教基督教（新教·天主教） / 约3.3亿人 / 关键词：个人主义、多元文化、自由平等"),
    ("de", "德国", "首都柏林 / 官方语言德语 / 主要宗教基督教（新教·天主教） / 约8400万人 / 关键词：严谨、守时、秩序"),
    ("jp", "日本", "首都东京 / 官方语言日语 / 主要宗教神道教·佛教 / 约1.25亿人 / 关键词：礼仪、集体主义、敬业"),
    ("in", "印度", "首都新德里 / 官方语言印地语、英语 / 主要宗教印度教 / 约14亿人 / 关键词：宗教多元、家庭、传统"),
    ("gb", "英国", "首都伦敦 / 官方语言英语 / 主要宗教基督教（圣公会） / 约6800万人 / 关键词：绅士、幽默、传统"),
    ("fr", "法国", "首都巴黎 / 官方语言法语 / 主要宗教天主教 / 约6800万人 / 关键词：浪漫、美食、艺术"),
    ("it", "意大利", "首都罗马 / 官方语言意大利语 / 主要宗教天主教 / 约5900万人 / 关键词：家庭、热情、美食"),
    ("br", "巴西", "首都巴西利亚 / 官方语言葡萄牙语 / 主要宗教天主教 / 约2.1亿人 / 关键词：热情、狂欢、足球"),
    ("ca", "加拿大", "首都渥太华 / 官方语言英语、法语 / 主要宗教基督教 / 约4000万人 / 关键词：多元、礼貌、自然"),
    ("ru", "俄罗斯", "首都莫斯科 / 官方语言俄语 / 主要宗教东正教 / 约1.46亿人 / 关键词：豪爽、文学、坚韧"),
    ("mx", "墨西哥", "首都墨西哥城 / 官方语言西班牙语 / 主要宗教天主教 / 约1.29亿人 / 关键词：家庭、节庆、热情"),
    ("kr", "韩国", "首都首尔 / 官方语言韩语 / 主要宗教佛教·基督教 / 约5200万人 / 关键词：长幼有序、K文化、快节奏"),
    ("au", "澳大利亚", "首都堪培拉 / 官方语言英语 / 主要宗教基督教 / 约2700万人 / 关键词：随和、户外、多元"),
    ("es", "西班牙", "首都马德里 / 官方语言西班牙语 / 主要宗教天主教 / 约4800万人 / 关键词：热情、夜生活、节庆"),
    ("id", "印尼", "首都雅加达 / 官方语言印尼语 / 主要宗教伊斯兰教 / 约2.8亿人 / 关键词：多元、穆斯林、温和"),
    ("tr", "土耳其", "首都安卡拉 / 官方语言土耳其语 / 主要宗教伊斯兰教（逊尼派） / 约8500万人 / 关键词：好客、茶、东西交汇"),
    ("sa", "沙特阿拉伯", "首都利雅得 / 官方语言阿拉伯语 / 主要宗教伊斯兰教 / 约3600万人 / 关键词：宗教、待客、传统"),
    ("vn", "越南", "首都河内 / 官方语言越南语 / 主要宗教佛教 / 约1亿人 / 关键词：儒家影响、米粉、摩托"),
    ("my", "马来西亚", "首都吉隆坡 / 官方语言马来语 / 主要宗教伊斯兰教 / 约3400万人 / 关键词：多元种族、榴莲、穆斯林"),
    ("cn", "中国", "首都北京 / 官方语言汉语 / 儒释道多元信仰 / 约14亿人 / 关键词：家国一体、礼、人情、勤劳"),
]

# ---------------------------------------------------------------------------
# 文化习惯知识：3 维度 × 主题
# ---------------------------------------------------------------------------
CUSTOMS_DIMS = [
    ("culture", "文化习惯", [
        ("food", "饮食文化"), ("festival", "节庆习俗"), ("family", "家庭与社会"),
        ("time", "时间观念"), ("religion", "宗教与信仰生活"), ("hospitality", "送礼与款待"),
    ]),
    ("etiquette", "社交礼仪", [
        ("greeting", "见面礼节"), ("address", "称呼与称谓"), ("business", "商务礼仪"),
        ("table", "餐桌礼仪"), ("smalltalk", "交谈话题"), ("gesture", "数字与手势"),
    ]),
    ("taboo", "文化禁忌", [
        ("language", "语言禁忌"), ("behavior", "行为禁忌"), ("religion", "宗教禁忌"),
        ("number", "数字·颜色·符号"), ("gift", "礼物禁忌"), ("social", "社交雷区"),
    ]),
]

# ---------------------------------------------------------------------------
# 文化桥：6 维度 × 主题
# ---------------------------------------------------------------------------
BRIDGE_DIMS = [
    ("history", "历史纽带", [
        ("trade", "丝路与贸易往来"), ("envoy", "使节与文化交流"), ("diaspora", "移民与华人社群"), ("thought", "思想与宗教传播"),
    ]),
    ("values", "价值观共通", [
        ("family", "家庭观念"), ("collective", "集体与个人"), ("diligence", "勤劳与奋斗"), ("face", "面子与尊重"),
    ]),
    ("festival", "节日与习俗相通", [
        ("reunion", "岁末团圆"), ("ancestor", "祭祖追思"), ("rites", "婚丧礼俗"), ("feast", "节庆饮食"),
    ]),
    ("lifestyle", "饮食与生活方式", [
        ("tea", "茶与饮品"), ("staple", "主食与餐桌"), ("hosting", "待客之道"), ("cuisine", "饮食特色"),
    ]),
    ("exchange", "现代往来", [
        ("trade", "经贸合作"), ("education", "教育与留学"), ("tourism", "旅游往来"), ("popculture", "流行文化"),
    ]),
    ("rapport", "相处建议", [
        ("communication", "沟通风格"), ("negotiation", "商务与谈判"), ("gift", "送礼与雷区"), ("trust", "建立信任"),
    ]),
]


def make_node(nid: str, ntype: str, title: str, content: str = "", children: list | None = None) -> dict:
    node = {"id": nid, "type": ntype, "title": title, "content": content, "parentId": None}
    if children:
        node["children"] = children
        node["childIds"] = [c["id"] for c in children]
    return node


def attach(parent: dict, child: dict) -> None:
    child["parentId"] = parent["id"]
    parent.setdefault("children", []).append(child)
    parent["childIds"] = [c["id"] for c in parent["children"]]


def add_stats(node: dict) -> dict:
    """递归统计 parts/chapters/sections/skills（技能点由外部回填时更新）。"""
    counts = {"parts": 0, "chapters": 0, "sections": 0, "skills": 0}
    for c in node.get("children") or []:
        if c["type"] == "part":
            counts["parts"] += 1
        elif c["type"] == "chapter":
            counts["chapters"] += 1
        elif c["type"] == "section":
            counts["sections"] += 1
        elif c["type"] == "skill":
            counts["skills"] += 1
        sub = add_stats(c)
        for k in counts:
            counts[k] += sub[k]
    return counts


def finalize_tree(master: dict) -> dict:
    master["stats"] = {"title": master["title"], **add_stats(master)}
    return master


# ---------------------------------------------------------------------------
# 库 1：文化习惯知识
# ---------------------------------------------------------------------------
def build_customs_kb() -> dict:
    master = make_node("cc_master", "master", "总库", "跨文化知识库 · 文化习惯知识总库")
    book = make_node("cc_book_customs", "book", "文化习惯知识", "20 个国家的文化习惯 / 社交礼仪 / 文化禁忌")
    attach(master, book)

    for code, name, overview in COUNTRIES:
        country = make_node(f"cc__{code}", "part", name, overview)
        attach(book, country)
        for dim_key, dim_title, topics in CUSTOMS_DIMS:
            chapter = make_node(f"cc__{code}__{dim_key}", "chapter", dim_title, "")
            attach(country, chapter)
            for topic_key, topic_title in topics:
                section = make_node(f"cc__{code}__{dim_key}__{topic_key}", "section", topic_title, "")
                attach(chapter, section)

    return {
        "schemaVersion": "1.0",
        "name": "文化习惯知识",
        "root": finalize_tree(master),
        "skills": [],
    }


# ---------------------------------------------------------------------------
# 库 2：文化桥
# ---------------------------------------------------------------------------
def bridge_part_title(code: str, name: str) -> str:
    if code == "cn":
        return "中华文化锚点"
    short = {"us": "美", "de": "德", "jp": "日", "in": "印", "gb": "英", "fr": "法", "it": "意",
             "br": "巴", "ca": "加", "ru": "俄", "mx": "墨", "kr": "韩", "au": "澳", "es": "西",
             "id": "印尼", "tr": "土", "sa": "沙", "vn": "越", "my": "马"}.get(code, name[0])
    return f"中{short}文化桥"


def build_bridge_kb() -> dict:
    master = make_node("cc_master", "master", "总库", "跨文化知识库 · 文化桥总库")
    book = make_node("cc_book_bridge", "book", "文化桥", "中国与 19 国 + 中华文化锚点：共同点与相处建议")
    attach(master, book)

    for code, name, overview in COUNTRIES:
        part = make_node(f"cc__{code}__bridge", "part", bridge_part_title(code, name),
                         "中华文化锚点（对照基准）" if code == "cn" else f"中国 × {name} 文化共同点")
        attach(book, part)
        for dim_key, dim_title, topics in BRIDGE_DIMS:
            chapter = make_node(f"cc__{code}__bridge__{dim_key}", "chapter", dim_title, "")
            attach(part, chapter)
            for topic_key, topic_title in topics:
                section = make_node(f"cc__{code}__bridge__{dim_key}__{topic_key}", "section", topic_title, "")
                attach(chapter, section)

    return {
        "schemaVersion": "1.0",
        "name": "文化桥",
        "root": finalize_tree(master),
        "skills": [],
    }


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------
def validate(kb: dict, path: str) -> None:
    ids = set()
    problems = []

    def walk(node: dict) -> None:
        nid = node["id"]
        if nid in ids:
            problems.append(f"重复 ID: {nid}")
        ids.add(nid)
        for c in node.get("children") or []:
            if c.get("parentId") != nid:
                problems.append(f"parentId 错误: {c['id']} -> {c.get('parentId')} (应为 {nid})")
            walk(c)

    walk(kb["root"])
    child_ids = {cid for node in [kb["root"]] for cid in node.get("childIds", [])}
    # 校验 root.childIds 对应 book
    for nid in kb["root"].get("childIds", []):
        if nid not in ids:
            problems.append(f"childIds 指向不存在: {nid}")

    for s in kb.get("skills") or []:
        if s["id"] in ids:
            problems.append(f"skill ID 与树冲突: {s['id']}")
        if s.get("parentId") not in ids:
            problems.append(f"skill parentId 不存在: {s.get('parentId')}")

    stats = kb["root"]["stats"]
    print(f"  {path}: master/book/part/chapter/section = "
          f"1/1/{stats['parts']}/{stats['chapters']}/{stats['sections']}，节点总数 {len(ids)}，skills {len(kb['skills'])}")
    if problems:
        raise SystemExit("校验失败:\n" + "\n".join(problems))
    print("  ✓ 校验通过（ID 唯一、parentId/childIds 完整）")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    customs = build_customs_kb()
    bridge = build_bridge_kb()
    for name, kb in [("culture_customs_kb.json", customs), ("cultural_bridge_kb.json", bridge)]:
        out = DATA_DIR / name
        out.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已生成:", out)
        validate(kb, out.name)


if __name__ == "__main__":
    main()
