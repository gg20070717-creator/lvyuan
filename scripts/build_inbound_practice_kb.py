# -*- coding: utf-8 -*-
"""生成「入境游实战能力」知识库骨架（第 7 本书）。结构: master→book→part(行前/行中/行后)→chapter(维度)→section(主题)→skill。
skill 标题为注意事项式；content/key_points 由后续填充脚本生成（本脚本只建结构）。"""
from __future__ import annotations
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT = DATA_DIR / "inbound_practice_kb.json"

PLAN = {
    "pre": {"title": "行前", "chapters": {
        "interview": ("客户需求访谈", {
            "probe": ("需求挖掘追问", [
                "行前·访谈：开场破冰与建立安全感的话术",
                "行前·访谈：追问出行场景（家人朋友独自/庆祝节点）",
                "行前·访谈：追问兴趣偏好（自然人文美食/排除项）",
                "行前·访谈：追问节奏与体力（紧凑留白/出发时间）",
                "行前·访谈：追问过往旅行参考（好评差评环节）",
                "行前·访谈：追问底线与禁忌（绝对不去/不能错过）",
                "行前·访谈：一次只问一个维度的提问纪律",
                "行前·访谈：对方犹豫时给选项而非开放式问题",
            ]),
            "special": ("禁忌与特殊需求识别", [
                "行前·访谈：宗教饮食禁忌主动询问清单（伊斯兰/犹太/印度教/佛教）",
                "行前·访谈：过敏与健康需求识别（过敏原/用药/慢性病）",
                "行前·访谈：老人游客需求识别要点",
                "行前·访谈：儿童亲子需求识别要点",
                "行前·访谈：无障碍出行需求识别要点",
                "行前·访谈：商务加旅游混合需求记录要点",
            ]),
            "card": ("需求结构化（需求卡）", [
                "行前·需求卡：把访谈内容整理成结构化需求卡的步骤",
                "行前·需求卡：必填字段清单（人数天数预算偏好禁忌）",
                "行前·需求卡：与客户二次确认需求卡的注意事项",
            ]),
        }),
        "design": ("行程设计", {
            "modular": ("模块化组合", [
                "行前·设计：行程模块拆分的总体原则",
                "行前·设计：交通与住宿模块的设计要点",
                "行前·设计：活动与讲解模块的设计要点",
                "行前·设计：模块组合与行程节奏的注意事项",
            ]),
            "visafree": ("免签240小时产品设计", [
                "行前·设计：免签240小时的政策要点与适用范围",
                "行前·设计：免签240小时的停留时间计算与出入境核对",
                "行前·设计：免签240小时经典城市线路设计",
                "行前·设计：免签行程的证件与材料准备",
                "行前·设计：免签行程变更与突发应对",
            ]),
            "quote": ("快速报价", [
                "行前·报价：模块化报价的组成与口径",
                "行前·报价：报价单透明度与隐藏费用避让",
                "行前·报价：汇率波动对报价的影响",
                "行前·报价：支付方式与定金规则",
                "行前·报价：报价有效期与留价策略",
            ]),
        }),
        "itinerary": ("行程单结构化", {
            "fields": ("国际标准字段", [
                "行前·行程单：体能字段（海拔/步行距离/难度等级）的填写",
                "行前·行程单：健康字段（过敏原/无障碍/医疗设施）的填写",
                "行前·行程单：宗教与饮食字段（清真/洁食/素食）的填写",
                "行前·行程单：交通字段（车程/换乘/接送说明）的填写",
                "行前·行程单：天气与着装携带建议字段的填写",
                "行前·行程单：信息颗粒度的自查清单",
            ]),
            "theme": ("主题与分层", [
                "行前·行程单：单一主题产品定位的写法",
                "行前·行程单：基础舒适高端分层的设计",
                "行前·行程单：避免大包大揽的产品描述",
                "行前·行程单：面向国际分销与AI检索的关键词写法",
            ]),
        }),
    }},
    "mid": {"title": "行中", "chapters": {
        "pickup": ("接机接站", {
            "arrival": ("接机流程与核对", [
                "行中·接机：接机前信息核对清单（航班/时间/人数/举牌）",
                "行中·接机：航班延误取消的应对注意事项",
                "行中·接机：首次见面的问候与破冰话术要点",
                "行中·接机：接机位置与等待期间的沟通",
            ]),
            "connect": ("转机衔接", [
                "行中·接机：转机时间不足的应急处置",
                "行中·接机：行李丢失的引导处理要点",
                "行中·接机：换乘交通的衔接与告知",
            ]),
        }),
        "culture": ("跨文化讲解", {
            "coverage": ("讲解要点覆盖", [
                "行中·讲解：按技能点准备讲解要点的步骤",
                "行中·讲解：讲解结构（开场主体收尾）的设计",
                "行中·讲解：讲解节奏与时间分配的控制",
                "行中·讲解：互动提问与引导技巧",
                "行中·讲解：讲解内容的准确性核查",
            ]),
            "difference": ("文化差异应对", [
                "行中·讲解：欧美游客的讲解偏好",
                "行中·讲解：日韩游客的讲解偏好",
                "行中·讲解：东南亚南亚游客的讲解偏好",
                "行中·讲解：中东游客的讲解偏好（宗教敏感）",
                "行中·讲解：宗教场所参观的礼仪注意事项",
                "行中·讲解：文化误解现场的化解话术",
            ]),
        }),
        "handoff": ("项目衔接", {
            "hotel": ("酒店入住", [
                "行中·衔接：外宾酒店入住的证件与登记要点",
                "行中·衔接：酒店被无涉外资格拒接的应对",
                "行中·衔接：入住后注意事项告知清单",
                "行中·衔接：行李搬运与小费惯例",
            ]),
            "activity": ("景点活动衔接", [
                "行中·衔接：景区预约与门票核销的注意事项",
                "行中·衔接：活动衔接的时间冗余预留",
                "行中·衔接：行程变更时的沟通要点",
            ]),
            "transport": ("交通接驳", [
                "行中·衔接：跨城交通的接驳安排与告知",
                "行中·衔接：打车网约车的涉外使用注意事项",
                "行中·衔接：司机沟通与行程说明要点",
            ]),
        }),
        "compliance": ("涉外履约", {
            "payment": ("外卡支付", [
                "行中·支付：外卡刷卡失败的常见原因",
                "行中·支付：磁条卡芯片卡非接触支付的差异",
                "行中·支付：引导游客使用替代支付方式的要点",
                "行中·支付：手续费与金额门槛的提前告知",
                "行中·支付：支付失败现场的安抚与解决",
            ]),
            "booking": ("预约与证件", [
                "行中·预约：景区预约的护照号证件字段填写",
                "行中·预约：预约周期短的风险预案",
                "行中·预约：证件查验与复印留存的合规注意",
            ]),
            "qualification": ("涉外资格规则", [
                "行中·履约：酒店涉外资格拒接的合规口径",
                "行中·履约：不得以资质为由拒接外宾的规定",
                "行中·履约：遇到违规拒接时的维权与投诉指引",
            ]),
            "taxrefund": ("退税", [
                "行中·退税：离境退税的适用条件与流程",
                "行中·退税：退税商店覆盖不均的应对",
                "行中·退税：退税单填写与海关核验注意事项",
            ]),
            "digital": ("数字壁垒替代方案", [
                "行中·数字：Google与WhatsApp不可直连的替代方案",
                "行中·数字：国际游客上网的解决方案（eSIM/热点）",
                "行中·数字：APP注册实名绑卡的协助注意事项",
            ]),
        }),
        "emergency": ("应急响应", {
            "medical": ("医疗与安全", [
                "行中·应急：游客突发疾病的处置流程",
                "行中·应急：常见急症识别（中暑/食物中毒/心脏问题）",
                "行中·应急：急救电话与国际救援协调要点",
                "行中·应急：慢性病游客的行中关注要点",
                "行中·应急：用药与就医陪同的注意事项",
                "行中·应急：安全风险告知与免责说明",
            ]),
            "lost": ("财物丢失", [
                "行中·应急：护照丢失的挂失补办流程",
                "行中·应急：行李财物丢失的报案与协助",
                "行中·应急：盗窃现场的安抚与处理要点",
            ]),
            "delay": ("突发取消延误", [
                "行中·应急：航班行程延误的沟通与改签",
                "行中·应急：酒店活动临时取消的替代方案",
                "行中·应急：行程被迫中断的退款与补偿口径",
            ]),
            "complaint": ("投诉升级", [
                "行中·应急：现场投诉升级的降火话术",
                "行中·应急：投诉记录的规范留存",
                "行中·应急：上报与转交的边界注意事项",
            ]),
        }),
    }},
    "post": {"title": "行后", "chapters": {
        "complaint": ("客诉处理", {
            "response": ("投诉响应流程", [
                "行后·客诉：投诉受理的标准响应流程",
                "行后·客诉：48小时内回访的注意事项",
                "行后·客诉：投诉分级标准（轻中重）",
                "行后·客诉：升级上报流程与权限边界",
            ]),
            "appease": ("安抚与补偿话术", [
                "行后·客诉：安抚情绪的共情话术要点",
                "行后·客诉：先听后给的补偿节奏",
                "行后·客诉：补偿方案的种类与边界",
                "行后·客诉：避免承诺过头的红线",
            ]),
            "negative": ("差评应对", [
                "行后·客诉：TripAdvisor差评的回应模板",
                "行后·客诉：Google差评的回应模板",
                "行后·客诉：差评回应的红线与禁忌",
                "行后·客诉：差评转私聊处理的注意事项",
            ]),
        }),
        "review": ("平台信用运营", {
            "positive": ("好评引导", [
                "行后·信用：合规的好评引导话术（避免索评违规）",
                "行后·信用：提留评的适当时机",
                "行后·信用：留评流程简化的操作建议",
            ]),
            "listing": ("Listing优化", [
                "行后·信用：TripAdvisor的listing信息完善要点",
                "行后·信用：Google商家listing信息完善要点",
                "行后·信用：照片描述标签优化的注意事项",
                "行后·信用：回复率与响应速度对排名的影响",
            ]),
            "followup": ("回访", [
                "行后·信用：行程结束后的回访话术与时机",
                "行后·信用：回访收集改进意见的要点",
                "行后·信用：节日纪念日触达的注意事项",
            ]),
        }),
        "referral": ("复购与转介绍", {
            "repurchase": ("复购经营", [
                "行后·复购：识别复购机会的信号",
                "行后·复购：老客户专属优惠的给法",
                "行后·复购：客户关系档案的维护要点",
            ]),
            "referral": ("转介绍话术", [
                "行后·转介：开口请转介绍的时机与话术",
                "行后·转介：转介绍激励的合规设计",
                "行后·转介：把好评客户变成口碑源头的要点",
            ]),
        }),
    }},
}


def make_node(nid, ntype, title, content="", children=None):
    node = {"id": nid, "type": ntype, "title": title, "content": content, "parentId": None}
    if children:
        node["children"] = children
        node["childIds"] = [c["id"] for c in children]
    return node


def attach(parent, child):
    child["parentId"] = parent["id"]
    parent.setdefault("children", []).append(child)
    parent["childIds"] = [c["id"] for c in parent["children"]]


def add_stats(node):
    c = {"parts": 0, "chapters": 0, "sections": 0, "skills": 0}
    for ch in node.get("children") or []:
        t = ch["type"]
        if t == "part": c["parts"] += 1
        elif t == "chapter": c["chapters"] += 1
        elif t == "section": c["sections"] += 1
        elif t == "skill": c["skills"] += 1
        sub = add_stats(ch)
        for k in c: c[k] += sub[k]
    return c


def build():
    master = make_node("ib_master", "master", "总库", "入境游实战能力总库")
    book = make_node("ib__book", "book", "入境游实战能力",
                     "行前/行中/行后 实战能力：需求访谈、行程设计、履约、应急、客诉、信用运营（注意事项式技能点）")
    attach(master, book)
    n_skill = 0
    for part_key, part_cfg in PLAN.items():
        part = make_node(f"ib__{part_key}", "part", part_cfg["title"], "")
        attach(book, part)
        for ch_key, (ch_title, sections) in part_cfg["chapters"].items():
            chapter = make_node(f"ib__{part_key}__{ch_key}", "chapter", ch_title, "")
            attach(part, chapter)
            for sec_key, (sec_title, titles) in sections.items():
                section = make_node(f"ib__{part_key}__{ch_key}__{sec_key}", "section", sec_title, "")
                attach(chapter, section)
                for i, t in enumerate(titles):
                    sk = make_node(f"{section['id']}_{i:03d}", "skill", t, "")
                    sk["key_points"] = []
                    attach(section, sk)
                    n_skill += 1
    master["stats"] = {"title": master["title"], **add_stats(master)}
    book["stats"] = {"title": book["title"], **add_stats(book)}
    flat = []
    def walk(node):
        if node["type"] == "skill":
            flat.append(node); return
        for c in node.get("children") or []:
            walk(c)
    walk(master)
    kb = {"schemaVersion": "1.0", "name": "入境游实战能力", "root": master, "skills": flat}
    OUT.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已生成:", OUT)
    print("stats:", master["stats"])
    print("技能点总数:", n_skill)


if __name__ == "__main__":
    build()