"""初试引导 → 先验画像 → 学习路径规划（M1 后端核心，纯逻辑可测）。

口径（已与产品确认）：
- 知识域 = 知识树第 1 层（book），共 7 个；
- 分组   = 知识树第 2 层（book 的直接子节点：有 part 用 part，没有则用 chapter），共 84 个；
- 自评状态：mastered(已掌握/不需要) / learning(要学/未掌握)；
- mastered → 该组所有技能点写 baseline=100（先验点亮）；learning → 不写 baseline，按真实作答动态算；
- 学习路径：管家排 84 个分组的顺序 → 硬编码校验（排全、格式可解析、ID 可对应）→
  按管家顺序把组内技能点按树序连成一条线；mastered 组的技能点整体放在初始位置之前。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# ── 自评状态语义 ──
STATUS_MASTERED = "mastered"        # 已掌握 / 不需要 → baseline 100
STATUS_LEARNING = "learning"        # 要学 / 未掌握 → 0，进入学习路线
STATUS_ALIAS_MASTERED = {"mastered", "skipped", "not_needed", "已掌握", "不需要", "跳过"}


# ── 第一层：6 道身份题（定制入境游向导培训，不预设“考导游证”） ──
IDENTITY_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "identity",
        "question": "你现在更接近以下哪种身份？",
        "options": [
            {"id": "student", "label": "在校学生（旅游/外语/导游相关专业）"},
            {"id": "travel_worker", "label": "旅行社/OTA/定制机构从业者（计调、定制师、销售、领队/OP）"},
            {"id": "guide", "label": "导游/讲解员（含持证与未持证，带过团）"},
            {"id": "language", "label": "外语人才/留学生/有海外生活经历者（想入入境游）"},
            {"id": "career_switcher", "label": "跨行业想转型做入境游向导/定制接待"},
            {"id": "culture_worker", "label": "文旅/研学/会展/景区从业者"},
        ],
    },
    {
        "id": "basis",
        "question": "你现在的带团/接待经验更接近哪种？",
        "options": [
            {"id": "zero", "label": "没带过团，也没做过入境接待"},
            {"id": "partial", "label": "学过一些/实习跟过团，没独立带过"},
            {"id": "experienced", "label": "带过中文团/国内地接，想学入境游与定制接待"},
            {"id": "retaker", "label": "接过外国游客/跟过入境团，想系统补上"},
            {"id": "guide_return", "label": "以前带过团（含入境），想重拾并升级定制接待"},
        ],
    },
    {
        "id": "language",
        "question": "你的外语水平更接近哪一种？（入境接待很看重这项）",
        "options": [
            {"id": "none", "label": "只会中文（先做中文讲解/跟团学习）"},
            {"id": "basic", "label": "基础外语：能打招呼/简单交流，接外宾吃力"},
            {"id": "fluent", "label": "外语流利：可独立接待外国游客（英日韩法西德等）"},
            {"id": "minority", "label": "外语之外还懂小语种，想发挥语言优势"},
        ],
    },
    {
        "id": "goal",
        "question": "你最想提升/从事的方向是？",
        "options": [
            {"id": "inbound_foreign", "label": "入境游接待 / 外语讲解（外国游客来华）"},
            {"id": "custom_high", "label": "定制旅行 / 高端入境定制（免签240小时、主题深度）"},
            {"id": "product_plan", "label": "行程设计/产品与报价（偏幕后）"},
            {"id": "outbound_leader", "label": "领队 / 团队与带队管理"},
            {"id": "cert_cn", "label": "需要报考导游资格证（作为入行/进阶资质）"},
            {"id": "undecided", "label": "还没想清楚，先把能力和知识系统补起来"},
        ],
    },
    {
        "id": "pace",
        "question": "你实际能投入的学习节奏是？",
        "options": [
            {"id": "fulltime", "label": "可沉浸式/较密集学习（几天集中+持续巩固）"},
            {"id": "parttime", "label": "在职，每周固定时间系统学"},
            {"id": "flex", "label": "时间碎片化，随学随练"},
            {"id": "longterm", "label": "不赶时间，长期稳步提升、重实战"},
        ],
    },
    {
        "id": "style",
        "question": "你更喜欢哪种学习/训练方式？",
        "options": [
            {"id": "quiz", "label": "多练习多测评，及时反馈"},
            {"id": "lecture", "label": "先讲清楚原理再用（讲义/讲解）"},
            {"id": "practice", "label": "真实场景演练（对话/沙盒/模拟接待）"},
            {"id": "coached", "label": "带学+计划督促，跟着节奏走"},
        ],
    },
]

_PERSONA_META: dict[str, dict[str, str]] = {
    "student": {"label": "旅游/外语在校生", "desc": "有专业底子但缺实战场，需要系统过知识与技能点，再用入境游接待/定制实战把它练熟。"},
    "travel_worker": {"label": "旅业从业者", "desc": "懂产品/渠道但缺一线讲解与跨文化接待能力，重点补接待流程+入境游实战+行程设计。"},
    "guide": {"label": "导游 / 讲解员", "desc": "有带团功底，缺系统理论与跨文化/定制接待升级；按需补法规理论+外语入境+定制设计。"},
    "language": {"label": "外语跨界人才", "desc": "语言是优势，缺行业规则、景点讲解与接待流程；重点补入境接待实战+文化习惯/文化桥。"},
    "career_switcher": {"label": "跨行转行新人", "desc": "几乎零基础，从 0 系统学并靠带学/计划坚持下来，先补通用带团与入境接待基本功。"},
    "culture_worker": {"label": "文旅/研学/会展从业者", "desc": "有相关经验但缺讲解带团与涉外接待能力，按需补资质并精进专项。"},
}

_GOAL_LABEL = {
    "inbound_foreign": "入境游接待 / 外语讲解",
    "custom_high": "定制旅行 / 高端入境定制",
    "product_plan": "行程设计 / 产品与报价",
    "outbound_leader": "领队 / 带队管理",
    "cert_cn": "报考导游资格证（资质）",
    "undecided": "先补能力，方向再定",
}
_LANG_LABEL = {"none": "只会中文", "basic": "基础外语", "fluent": "外语流利", "minority": "含小语种"}
_PACE_LABEL = {"fulltime": "沉浸式/密集学", "parttime": "每周固定学", "flex": "碎片化随学随练", "longterm": "长期重实战"}
_STYLE_LABEL = {"quiz": "多练多测", "lecture": "先讲再用", "practice": "场景演练", "coached": "带学督促"}


# ── 知识域/分组索引（第 2 层分组 = 84） ──
@dataclass
class GroupInfo:
    id: str
    title: str
    type: str            # part / chapter
    book_id: str
    book_title: str
    skill_ids: list[str] = field(default_factory=list)

    @property
    def skill_count(self) -> int:
        return len(self.skill_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "type": self.type,
            "book_id": self.book_id, "book_title": self.book_title,
            "skill_ids": list(self.skill_ids), "skill_count": self.skill_count,
        }


def build_group_index(plugin: Any) -> dict[str, Any]:
    """从插件知识树构建：domains(7) × groups(84)，组内技能点按树序（DFS）。"""
    try:
        books = plugin._kb.books  # noqa: SLF001
    except Exception:
        books = []
    domains: list[dict[str, Any]] = []
    group_index: dict[str, GroupInfo] = {}
    order: list[str] = []

    def dfs_skill_ids(node: dict[str, Any], acc: list[str]) -> None:
        for ch in node.get("children") or []:
            if ch.get("type") == "skill":
                acc.append(ch["id"])
            else:
                dfs_skill_ids(ch, acc)

    for book in books:
        btitle = book.get("title") or ""
        groups: list[GroupInfo] = []
        for child in book.get("children") or []:
            if child.get("type") not in ("part", "chapter"):
                continue
            sids: list[str] = []
            dfs_skill_ids(child, sids)
            gi = GroupInfo(
                id=child.get("id", ""), title=child.get("title", ""),
                type=child.get("type", ""), book_id=book.get("id", ""),
                book_title=btitle, skill_ids=sids,
            )
            groups.append(gi)
            group_index[gi.id] = gi
            order.append(gi.id)
        domains.append({
            "id": book.get("id", ""), "title": btitle,
            "book_type": book.get("type", "book"),
            "groups": [g.to_dict() for g in groups],
        })
    return {"domains": domains, "groups": group_index, "order": order}


def _group_ids_of_books(group_index: dict[str, GroupInfo], book_titles: set[str]) -> list[str]:
    return [gid for gid, gi in group_index.items() if gi.book_title in book_titles]


# ── 先验画像（persona） ──
def build_persona(answers: dict[str, str]) -> dict[str, Any]:
    """由 6 道身份题生成结构化画像与『默认已掌握分组』预填。"""
    identity = answers.get("identity") or "student"
    basis = answers.get("basis") or "zero"
    language = answers.get("language") or "none"
    goal = answers.get("goal") or "cert_cn"
    pace = answers.get("pace") or "fulltime"
    style = answers.get("style") or "quiz"

    meta = _PERSONA_META.get(identity, _PERSONA_META["student"])
    # 目标方向叠加细化
    if identity == "guide" and goal in ("inbound_foreign", "custom_high"):
        persona_id = "guide_inbound"
        label = "老导游 · 入境游升级"
    elif identity == "language" and language in ("fluent", "minority"):
        persona_id = "language_inbound"
        label = "外语人才 · 入境游方向"
    else:
        persona_id = identity
        label = meta["label"]
    desc = meta["desc"]
    if goal in ("inbound_foreign", "custom_high"):
        desc += " 目标偏入境游/定制方向，跨文化与涉外履约会进入路线重点。"
    elif goal == "outbound_leader":
        desc += " 目标为出境领队，出境服务程序是重点。"

    summary = (
        f"{label}｜{_GOAL_LABEL.get(goal, goal)}｜外语：{_LANG_LABEL.get(language, language)}｜"
        f"节奏：{_PACE_LABEL.get(pace, pace)}｜偏好：{_STYLE_LABEL.get(style, style)}"
    )
    return {
        "persona_id": persona_id,
        "label": label,
        "summary": summary,
        "description": desc,
        "identity": identity,
        "basis": basis,
        "language": language,
        "goal": goal,
        "pace": pace,
        "style": style,
        # 默认已掌握的书（经验型老导游 → 导游业务全组预填 mastered，可自行改）
        "default_master_books": ["导游业务"] if (identity == "guide" or basis in ("experienced", "guide_return")) else [],
    }


def default_group_status(persona: dict[str, Any], group_index: dict[str, GroupInfo]) -> dict[str, str]:
    """persona 默认预填：mastered 的书 → 该 domain 全组 mastered，其余 learning。"""
    mb = set(persona.get("default_master_books") or [])
    return {gid: (STATUS_MASTERED if gi.book_title in mb else STATUS_LEARNING)
            for gid, gi in group_index.items()}


def normalize_status(v: str) -> str:
    if not v:
        return STATUS_LEARNING
    s = str(v).strip().lower()
    if s in STATUS_ALIAS_MASTERED:
        return STATUS_MASTERED
    return STATUS_LEARNING


# ── baseline 落库（先验点亮） ──
def apply_baseline(store: Any, user_id: str, group_status: dict[str, str],
                   group_index: dict[str, GroupInfo]) -> dict[str, Any]:
    """按 84 组自评写 baseline：
    mastered → 该组全部技能点 baseline=100；learning → 清除旧 baseline（按客观/主观动态算）。
    """
    store.clear_mastery_kind(user_id, "baseline")
    mastered_groups: list[str] = []
    mastered_skills = 0
    for gid, gi in group_index.items():
        st = normalize_status((group_status or {}).get(gid, STATUS_LEARNING))
        if st == STATUS_MASTERED:
            mastered_groups.append(gid)
            for sid in gi.skill_ids:
                store.save_mastery_assessment(user_id, sid, "baseline", 100.0,
                                              note="初试画像·已掌握/不需要")
                mastered_skills += 1
    return {"mastered_groups": mastered_groups, "mastered_group_count": len(mastered_groups),
            "mastered_skills": mastered_skills,
            "learning_group_count": len(group_index) - len(mastered_groups)}


# ── 学习路径：管家输出解析 + 校验 + 展开 ──
_GROUP_ID_RE = re.compile(r"[A-Za-z0-9_:\.\-]{3,}")
_LINE_ITEM_RE = re.compile(r"^\s*(?:\d+[\.、\)]\s*)?([A-Za-z0-9_:\.\-]+)\s*[:：\-]?\s*(.*)$")


def parse_group_order(text: str, group_index: dict[str, GroupInfo],
                      fallback_titles: bool = True) -> tuple[list[str], list[str]]:
    """把管家输出解析为 84 分组 ID 列表。

    支持两种格式：
    1) JSON 数组：["g1","g2",...] 或 [{"id":"g1","title":...},...]
    2) 每行一项：`序号. 分组ID 标题`（可只给 ID，也可只给标题）。
    返回 (ids, errors)。
    """
    errors: list[str] = []
    title2id = {gi.title: gid for gid, gi in group_index.items()}
    t = (text or "").strip()
    ids: list[str] = []

    # 尝试 JSON 数组
    try:
        arr = json.loads(t)
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, str):
                    ids.append(item.strip())
                elif isinstance(item, dict):
                    i = (item.get("id") or item.get("group_id") or "").strip()
                    ids.append(i)
            return ids, errors
    except Exception:
        pass

    for line in t.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//", "分组", "顺序")):
            continue
        m = _LINE_ITEM_RE.match(line)
        if not m:
            continue
        cand = m.group(1).strip()
        rest = (m.group(2) or "").strip()
        if cand in group_index:
            ids.append(cand)
            continue
        if rest in title2id:
            ids.append(title2id[rest])
            continue
        # 整行就是标题
        if line in title2id:
            ids.append(title2id[line])
            continue
        errors.append(f"无法识别：{line[:60]}")
    return ids, errors


def validate_group_order(ordered_ids: list[str], group_index: dict[str, GroupInfo]) -> dict[str, Any]:
    canonical = list(group_index.keys())
    uniq: list[str] = []
    seen: set[str] = set()
    unknown: list[str] = []
    for i in ordered_ids:
        i = (i or "").strip()
        if i not in group_index:
            unknown.append(i)
        elif i not in seen:
            seen.add(i)
            uniq.append(i)
    missing = [g for g in canonical if g not in seen]
    ok = (not unknown) and (len(missing) == 0) and (len(uniq) == len(canonical))
    return {"ok": ok, "ordered": uniq, "count": len(uniq), "total": len(canonical),
            "missing": missing, "unknown": unknown[:20]}


def expand_plan(ordered_group_ids: list[str], group_index: dict[str, GroupInfo],
                mastered_group_ids: set[str]) -> dict[str, Any]:
    """把 84 组顺序展开成技能点线性路径：
    - before_start：mastered（已掌握/不需要）组技能点，先放（均 100，位于初始位置之前）
    - path：learning 组按管家顺序展开的技能点（DFS 树序）
    """
    before: list[str] = []
    path: list[str] = []
    for gid in ordered_group_ids:
        gi = group_index.get(gid)
        if not gi:
            continue
        if gid in mastered_group_ids:
            before.extend(gi.skill_ids)
        else:
            path.extend(gi.skill_ids)
    return {"before_start": before, "path": path,
            "total": len(before) + len(path),
            "before_start_count": len(before), "path_count": len(path)}


def build_route_record(user_id: str, ordered_group_ids: list[str], group_index: dict[str, GroupInfo],
                       mastered_group_ids: set[str], note: str = "") -> dict[str, Any]:
    expanded = expand_plan(ordered_group_ids, group_index, mastered_group_ids)
    groups_seq = [group_index[g].to_dict() for g in ordered_group_ids if g in group_index]
    return {
        "user_id": user_id,
        "group_order": list(ordered_group_ids),
        "groups": groups_seq,
        "before_start_skill_ids": expanded["before_start"],
        "path_skill_ids": expanded["path"],
        "stats": {"groups": len(groups_seq), "before_start": expanded["before_start_count"],
                  "learning_path": expanded["path_count"], "total_skills": expanded["total"]},
        "note": note or "",
    }


# ── M1b：路线排序（管家排 84 组 → 校验 → 重试 → 落库） ──
_ROUTE_SYSTEM = (
    "你是学习路径规划师，负责把学员的全部 84 个知识分组排成一条科学的学习路线。"
    "你手里有学员画像与『默认已掌握』的分组（这些组技能点已点亮、会放到路线最前面，你不用特别处理）。"
    "排序原则：基础→应用→综合；全国导游资格四科理论在前，跨文化/文化桥用于入境接待前铺垫，"
    "入境游实战（行前/行中/行后）放后段用于综合实战；同域内按认知依赖排，勿打乱同书内的章/部内部顺序。"
    "输出铁律：只输出 84 行，每行格式『序号. 分组ID 分组标题』，一行一个，"
    "必须覆盖下面给出的全部 84 个分组、不许新增、不许重复、不许解释、不许用其它格式。"
)


def _route_groups_block(group_index: dict[str, GroupInfo]) -> str:
    lines = []
    for gid in group_index["order"]:
        gi = group_index["groups"][gid]
        lines.append(f"{gi.book_title} / {gi.title}  id={gid}  ({gi.skill_count} 技能点)")
    return "\n".join(lines)


def plan_route(
    llm: Any,
    group_index: dict[str, GroupInfo],
    persona: dict[str, Any],
    defaults: dict[str, str],
    feedback: str = "",
    max_attempts: int = 3,
    fallback: bool = True,
) -> dict[str, Any]:
    """让规划模型把 84 组分组成一条路线；校验不合格自动带错因重排。

    llm 需支持 generate(system, user) -> {content}（LLMClient 兼容）。
    返回：{ok, attempts, order, validation, fallback, error}
    """
    mastered_ids = [gid for gid, st in defaults.items() if normalize_status(st) == STATUS_MASTERED]
    mastered_titles = "、".join(
        group_index["groups"][g].title for g in mastered_ids if g in group_index["groups"]
    ) or "（无）"
    user_head = (
        f"学员画像：{persona.get('summary') or ''}\n"
        f"{persona.get('description') or ''}\n"
        f"默认已掌握分组：{mastered_titles}\n"
        "请为下面 84 个分组排学习顺序（行数=84）：\n"
    )
    body = _route_groups_block(group_index)
    last_error = ""
    used = []
    for attempt in range(1, max_attempts + 1):
        user = user_head + body
        if last_error:
            user += f"\n\n上一次排序未通过，原因：{last_error}。请修正后重新完整输出 84 行。"
        if feedback:
            user += f"\n\n学员补充要求（务必体现在顺序上）：{feedback}"
        try:
            resp = llm.generate(_ROUTE_SYSTEM, user, temperature=0.3, max_tokens=6000)
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as exc:  # noqa: BLE001
            last_error = f"模型调用失败：{exc}"
            used.append({"attempt": attempt, "error": last_error})
            continue
        ids, errs = parse_group_order(text, group_index["groups"])
        used.append({"attempt": attempt, "error": last_error or None})
        val = validate_group_order(ids, group_index["groups"])
        if val["ok"]:
            return {"ok": True, "attempts": attempt, "order": val["ordered"],
                    "validation": val, "fallback": False, "error": "", "usage": used}
        # 组错因
        parts = []
        if val["missing"]:
            parts.append("缺 " + str(len(val["missing"])) + " 组：" + "、".join(val["missing"][:5]))
        if val["unknown"]:
            parts.append("包含未知ID：" + "、".join(val["unknown"][:5]))
        if errs:
            parts.append("；".join(errs[:3]))
        last_error = "；".join(parts) if parts else "格式无法解析"
    if fallback:
        canonical = list(group_index["order"])
        val = validate_group_order(canonical, group_index["groups"])
        return {"ok": True, "attempts": max_attempts, "order": canonical,
                "validation": val, "fallback": True,
                "error": "多次校验未通过，已按知识树默认顺序兜底：" + last_error, "usage": used}
    return {"ok": False, "attempts": max_attempts, "order": [], "fallback": False,
            "validation": None, "error": last_error, "usage": used}


def plan_to_route(user_id: str, plan: dict[str, Any], group_index: dict[str, GroupInfo],
                  defaults: dict[str, str], note: str = "") -> dict[str, Any]:
    """把 plan_route 结果组装为 learning_path 路由记录。

    group_index 为 build_group_index() 的完整返回（含 order/groups）；内部解包 groups。
    """
    groups = group_index["groups"] if isinstance(group_index, dict) and "groups" in group_index else group_index
    mastered_ids = {gid for gid, st in defaults.items() if normalize_status(st) == STATUS_MASTERED}
    return build_route_record(user_id, plan.get("order") or [], groups,
                              mastered_group_ids=mastered_ids, note=note or "")

# ── M2b：画像 / 盲区 的“管家解读”（LLM + 确定性兜底） ──
def build_insight_fallback(persona: dict[str, Any], blindspots: list[dict[str, Any]]) -> dict[str, str]:
    p = persona or {}
    pace = _PACE_LABEL.get(p.get('pace',''), p.get('pace',''))
    style = _STYLE_LABEL.get(p.get('style',''), p.get('style',''))
    lang = _LANG_LABEL.get(p.get('language',''), p.get('language',''))
    goal = _GOAL_LABEL.get(p.get('goal',''), p.get('goal',''))
    pa = (
        f"【一、学员定位】你当前被识别为「{p.get('label') or '待定'}」型学员。{p.get('description') or ''}\n"
        f"语言条件：{lang}；目标方向：{goal}；可投入节奏：{pace}；偏好学习方式：{style}。\n\n"
        f"【二、画像自评】在 7 大知识域、84 个分组的能力自评中，你明确勾选为“要学”的分组，是本次培训的主攻范围；"
        f"已掌握/跳过的分组会被自动点亮并放到学习路线最前，作为你的“会用但不必重学”的部分。\n\n"
        f"【三、成长建议】你的学习重点应围绕目标方向展开：先把通用带团与接待流程补扎实，再进入跨文化/文化桥铺垫，"
        f"最后用入境游实战（行前/行中/行后沙盒）把能力串成可交付的接待能力。"
    )
    if blindspots:
        top = blindspots[0]
        bd = (
            f"【盲区总览】系统为你定位了 {len(blindspots)} 个重点盲区分组，最需要优先处理的是"
            f"「{top.get('book_title','')} · {top.get('group_title','')}」：该组共 {top.get('skills_total',0)} 个技能点，"
            f"仍有 {top.get('weak_skills',0)} 个未点亮，平均掌握仅 {top.get('avg_mastery',0)}%。\n\n"
            f"【成因分析】这类盲区通常是“自评要学但还没有真正练到”：既没让司南系统讲过，也还没把该组的固定题做对。"
            f"知识停留在“知道”，没有落到“能做”，所以掌握度停留在低位。\n\n"
            f"【影响】它会拖住同主题后续技能点的解锁进度（导学模式下前一技能点需≥60%才能进入下一题/下一组）。"
        )
        others = "；".join(
            f"{b.get('book_title','')}·{b.get('group_title','')}(差{b.get('weak_skills',0)}点)"
            for b in blindspots[1:5]
        )
        if others:
            bd += f"\n\n【其次跟进】{others}。"
        actions = (
            f"① 打开“学习路线规划”，从当前位置所在组开始：先让司南讲解 1-2 个技能点，再用该技能点的固定题巩固到点亮；\n"
            f"② 重点先清「{top.get('book_title','')} · {top.get('group_title','')}」，它缺口最大、性价比最高；\n"
            f"③ 每点亮一组，回到学情中心看“学习盲区”是否减少，再进入下一组。"
        )
    else:
        bd = "【盲区总览】当前没有明显的盲区分组——你自评要学的分组都已逐步点亮，学习节奏健康。\n\n【建议】不必贪多，继续保持按路线逐点推进即可。"
        actions = "① 保持当前节奏，按学习路线逐组推进；② 可切“自由浏览”挑感兴趣的薄弱主题加练；③ 用沙盒做一次实战检验，把掌握度落到“能做”。"
    return {"persona_analysis": pa, "blindspot_analysis": bd, "next_actions": actions}


_INSIGHT_SYSTEM = (
    "你是资深入境游向导培训导师，根据学员画像、盲区定位与学习数据，写一份简洁、具体、可执行的学情解读。"
    "只输出 JSON，形如：{\"persona_analysis\":\"画像总评含优势与短板\",\"blindspot_analysis\":\"盲区解读，挑最该补的2-3处说明原因\",\"next_actions\":\"接下来1-2步做什么\"}。"
    "总字数控制在260字内，语气像给学员的贴身分析。"
)


def generate_insight(llm: Any, persona: dict[str, Any], blindspots: list[dict[str, Any]]) -> dict[str, str]:
    try:
        spot_txt = "；".join(
            f"{b.get('book_title','')}·{b.get('group_title','')}({b.get('weak_skills',0)}/{b.get('skills_total',0)}未点亮,平均{b.get('avg_mastery',0)}%)"
            for b in blindspots[:6]
        ) or "（无）"
        user = (
            f"画像：{(persona or {}).get('summary') or ''}\n{(persona or {}).get('description') or ''}\n"
            f"盲区：{spot_txt}\n请输出 JSON 解读。"
        )
        resp = llm.generate(_INSIGHT_SYSTEM, user, temperature=0.4, max_tokens=1200, response_format={"type": "json_object"})
        txt = resp.content if hasattr(resp, "content") else str(resp)
        import json as _json
        data = _json.loads(txt)
        return {
            "persona_analysis": str(data.get("persona_analysis") or ""),
            "blindspot_analysis": str(data.get("blindspot_analysis") or ""),
            "next_actions": str(data.get("next_actions") or ""),
        }
    except Exception:
        return build_insight_fallback(persona, blindspots)


# ── 盲区定位（学情中心顶部醒目展示） ──
def compute_domain_snapshot(
    store: Any, plugin: Any, user_id: str,
    group_index: dict[str, GroupInfo], weak_limit: int = 8,
) -> dict[str, Any]:
    """一次扫描得到：7 个知识域综合掌握度（雷达图）+ 每域分组进度明细（点端点下钻）。

    掌握度逐技能点用 MasteryService（缓存后较快）。返回：
    {domains:[{id,title,avg_mastery,groups:[{id,title,mastered,avg_mastery,weak_skills,skills_total}]}],
     weak:[...盲区分组排序]}
    """
    try:
        from brain_of_cloud.services.mastery import MasteryService
        ms = MasteryService(plugin, store)
    except Exception:
        ms = None
    profile = store.get_onboarding_profile(user_id)
    gs = (profile or {}).get("group_status") or {}
    groups = group_index["groups"] if isinstance(group_index, dict) and "groups" in group_index else group_index
    # 域名顺序（按 group_index["order"] 出现的 book 顺序）
    domains: list[dict[str, Any]] = []
    dmap: dict[str, dict[str, Any]] = {}
    for gi in groups.values():
        bid = gi.book_id
        if bid not in dmap:
            d = {"id": bid, "title": gi.book_title, "_sum": 0.0, "_cnt": 0, "groups": []}
            dmap[bid] = d
            domains.append(d)
        mastered = normalize_status(gs.get(gi.id, STATUS_LEARNING)) == STATUS_MASTERED
        vals: list[float] = []
        weak = 0
        for sid in (gi.skill_ids or []):
            try:
                m = float(ms.skill_mastery(user_id, sid)["mastery"]) if ms else 0.0
            except Exception:
                m = 0.0
            vals.append(m)
            if m < 60.0:
                weak += 1
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        ginfo = {
            "id": gi.id, "title": gi.title, "mastered": mastered,
            "avg_mastery": round(avg, 1), "weak_skills": weak,
            "skills_total": len(vals),
        }
        dmap[bid]["groups"].append(ginfo)
        dmap[bid]["_sum"] += sum(vals)
        dmap[bid]["_cnt"] += len(vals)
    weak_all: list[dict[str, Any]] = []
    for d in domains:
        d["avg_mastery"] = round(d["_sum"] / d["_cnt"], 1) if d["_cnt"] else 0.0
        d.pop("_sum", None); d.pop("_cnt", None)
        for g in d["groups"]:
            if g["weak_skills"] > 0:
                weak_all.append({
                    "group_id": g["id"], "group_title": g["title"],
                    "book_title": d["title"], "book_id": d["id"],
                    "skills_total": g["skills_total"], "weak_skills": g["weak_skills"],
                    "avg_mastery": g["avg_mastery"],
                })
    weak_all.sort(key=lambda r: (-r["weak_skills"], r["avg_mastery"]))
    return {"domains": domains, "weak": weak_all[:weak_limit]}


def compute_blindspots(
    store: Any, plugin: Any, user_id: str,
    group_index: dict[str, GroupInfo], limit: int = 8,
) -> list[dict[str, Any]]:
    """盲区分组（后端解读用；前端雷达用 compute_domain_snapshot）。"""
    snap = compute_domain_snapshot(store, plugin, user_id, group_index, weak_limit=limit)
    return snap["weak"]



# ── 画像打通：把结构化先验画像(persona)回写到旧 learner_profiles，让管家上下文/材料生成也能读到 ──
_LEVEL_BY_BASIS = {
    "zero": "零基础", "partial": "有基础/初级", "experienced": "中级（行业经验）",
    "retaker": "中级偏实战", "guide_return": "资深（回岗精进）",
}

def sync_learner_profile(store: Any, user_id: str, persona: dict[str, Any], answers: dict[str, Any] | None = None) -> None:
    """用 onboarding persona 单向同步 learner_profiles（保留旧 created_at）。

    这样旧链路（管家上下文 / TextGenerator / 六帽红帽 / 学情中心旧头部）也能看到结构化画像。
    """
    try:
        from brain_of_cloud.domain.models import LearnerProfile
    except Exception:
        return
    from datetime import datetime, timezone
    try:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        existing = store.get_learner_profile(user_id)
        created = existing.created_at if existing else now

        p = persona or {}
        ans = answers or {}
        summary = str(p.get("summary") or "")
        desc = str(p.get("description") or "")
        background = summary
        if desc and desc not in background:
            background = (background + "。" + desc) if background else desc

        goal = str(p.get("goal") or "")
        target_role = _GOAL_LABEL.get(goal, goal or "定制入境游向导")
        basis = str(p.get("basis") or "")
        current_level = f"{p.get('label') or ''}｜{_LEVEL_BY_BASIS.get(basis, '')}".strip("｜")
        style = str(p.get("style") or "lecture")
        style_preferences = {"mode": _STYLE_LABEL.get(style, style)}
        baseline_scores: dict[str, float] = {}  # 结构化画像已存 onboarding_profiles，无需在旧表塞非数值
        prof = LearnerProfile(
            user_id=user_id, background=background,
            target_role=target_role, current_level=current_level,
            style_preferences=style_preferences, baseline_scores=baseline_scores,
            created_at=created, updated_at=now,
        )
        store.save_learner_profile(prof)
    except Exception:
        # 同步失败不影响主流程（先验画像已独立落库）
        pass
