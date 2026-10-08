from __future__ import annotations

import json
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.storage.sqlite import SQLiteStore
from brain_of_cloud.services.agent_catalog import trace_event

# 五维评估（与前端既有结算维度保持一致）
FIVE_DIMS = ["表达能力", "控场能力", "文化知识", "服务意识", "互动引导"]

# 入境定制游全流程：对应“分课”全部完成（有评分记录）才解锁“全流程”大沙盒
FULLFLOW_PREREQ: dict[str, list[str]] = {
    "t_ff_pre_trip": ["t_pre_l1", "t_pre_l2", "t_pre_l3"],
    "t_ff_mid_trip": ["t_mid_l1", "t_mid_l2", "t_mid_l3", "t_mid_l4", "t_mid_l5"],
    "t_ff_post_trip": ["t_post_l1", "t_post_l2", "t_post_l3", "t_post_l4"],
}

CUSTOMER_SYSTEM_PROMPT = """\
你是{name}，一位来自{country}的{age}岁游客，正在参加一次中国跟团游。
- 性格：{personality}
- 偏好：{preferences}
- 说话习惯与特点：{quirks}
- 隐藏诉求：{hidden}

【当前场景】
{opening}
你身处：{location}
当前带团阶段：{stage_title}
本阶段导游应该做到（你的期待）：{objective}

【你的处境】（这就是你现在正在做的事/处境——是你自己，不是别人）
{situation}

【你的心理状态】（必须忠实扮演，随对话持续变化）
- 信任度：{trust}/100（你有多信任这位导游）
- 当前情绪：{mood}
- 你对导游的不满/疑虑：{concerns}
- 你已对导游流露的信息：{revealed_note}

【你的记忆】（别忘记自己说过什么、导游做过什么）
{recap}

【角色规则】
1. 你始终以游客身份说话，绝不出戏，绝不充当教练或评估者。
2. **一对一原则（铁律）**：场景中只有你（游客）和导游两个人互动。
   当前场景里任何需要导游处理的情况——违规、争执、冒犯、突发状况——都是你自己的行为或你自己的处境，
   绝不是其他游客的。禁止提及「其他游客/旁边的游客/某位团友」，禁止让导游去劝阻或处理别人——
   你只能以自己为中心，与导游面对面对话。
3. 用自然口语化的中文回复，每次 1-3 句，带个人口音、称呼或口头禅，符合人设。
4. 认真回应导游刚才说的每一句话：导游做得好你表露出满意（信任上升），
   做得差你表露出困惑、不满或质疑（信任下降）。情绪差时话变少、语气变冲、甚至直接顶撞；
   情绪好时愿意配合、主动搭话。
5. 隐藏诉求随信任上升自然流露：信任 ≥70 时你会主动说出真正的顾虑；
   信任 <40 时你倾向不配合、找茬、甚至威胁投诉或离团。
6. 适时主动向导游提问、提要求或制造小麻烦，检验导游的服务能力。
7. 只有当导游上一句话已实质完成本阶段关键目标时 advanced 才为 true；
   否则保持 false，继续把本阶段对话展开，不要急于收尾。

只输出一个 JSON 对象，不要任何多余文字：
{{"reply": "你的回复", "mood": "满意"|"一般"|"不满"|"愤怒", "trust_delta": -30到30的整数, "reaction": "你对导游本轮行为的30字内评价", "hidden_revealed": true|false, "advanced": true|false}}
"""

EVALUATOR_SYSTEM_PROMPT = """\
你是导游资格证培训系统的沙盒模拟评估师。评估一位实习导游在一段真实场景模拟对话中的表现。

评估维度（每项 1-5 分，5 最好）：
- 表达能力：语言流畅、条理清晰、有感染力
- 控场能力：主导节奏、处理突发、稳住局面
- 文化知识：讲解准确、有深度、引用得当
- 服务意识：主动关怀、体察需求、耐心细致
- 互动引导：善于提问互动、调动游客、回应关切

附加观察（不计入总分，只写入报告，用于成长反馈）——文化桥：
- 依据① 共通点：学员是否结合游客的文化背景（国籍/偏好/说话特点）自然讲出中外文化共通点（家庭/节庆/饮食/价值观/待客等），讲了多少、是否贴合场景与对话时机；
- 依据② 真实性：所讲共通点是否真实准确，不虚构、不张冠李戴、不把个案当普遍。
- 输出 culture_bridge: {"score": 1-5, "summary": "一句话说明依据①/②的判断"}。它不参与 total 与五维计算。

评分要求：
- total 为 0-100 的综合分，与五维得分相称。
- strengths / weaknesses / suggestions 各给出 2-4 条，具体到对话中的真实言行，不要空泛套话。
- skill_keywords 给出 3-6 个与本次表现相关的导游知识/技能关键词（中文），用于关联知识库学习点。
- 特别注意游客的隐藏诉求是否被导游察觉并妥善处理，这是重要的加分/扣分点。

只输出一个 JSON 对象，不要任何多余文字：
{{"total": 88, "dims": {{"表达能力": 4, "控场能力": 4, "文化知识": 5, "服务意识": 5, "互动引导": 3}},
 "strengths": ["..."], "weaknesses": ["..."], "suggestions": ["..."], "skill_keywords": ["..."],
 "culture_bridge": {{"score": 3, "summary": "..."}}}}
"""



class SandboxError(ValueError):
    """沙盒业务异常（未知会话/模板、会话已结束等）。"""


@dataclass(frozen=True)
class SandboxStage:
    title: str
    objective: str  # 本阶段导游应达成的目标（既是人设期待，也是评估依据）
    guide_hint: str  # 给学员的静态知识提示
    kb_keywords: list[str] = field(default_factory=list)
    min_turns: int = 2  # 本阶段最少展开轮数（剧情充分展开后，目标达成才可推进）
    max_turns: int = 8  # 本阶段最大轮数（防呆上限：剧情卡住时兜底推进/触发事件）


@dataclass(frozen=True)
class CustomerProfile:
    name: str
    nationality: str
    age: str
    personality: str
    preferences: str
    quirks: str
    hidden: str  # 隐藏诉求（对学员不可见，评估时作为隐藏考点）
    # ── 游客多维人设（v3：动态生成，强化发言与个人属性相关性）──
    gender: str = ""
    occupation: str = ""  # 职业（与年龄/场景相符）
    health: str = ""  # 健康状况（影响体力/行动/需求）
    consumption: str = ""  # 消费习惯
    speech_style: str = ""  # 说话风格（口音/语速/用词）


@dataclass(frozen=True)
class SandboxTemplate:
    template_id: str
    mode: str  # scenario | narrate | route
    title: str
    location: str
    task: str
    difficulty: int
    category: str
    opening: str  # 情境开场（系统旁白，展示给学员）
    stages: list[SandboxStage]
    goals: list[tuple[str, float]]  # 五维评估侧重点（dim, weight）
    customer_pool: list[CustomerProfile]
    situation: str = ""  # 游客视角的自身处境（一对一原则：需要处理的情况都是「你」自己做的）


_TEMPLATES_CACHE: list[SandboxTemplate] | None = None
_TEMPLATE_MAP_CACHE: dict[str, SandboxTemplate] | None = None


def _load_templates() -> list[SandboxTemplate]:
    """惰性加载场景库（避免 sandbox ↔ sandbox_templates 循环导入）。"""
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is None:
        from brain_of_cloud.services.sandbox_templates import TEMPLATES
        from brain_of_cloud.services.communication_templates import TEMPLATES as COMMUNICATION

        _TEMPLATES_CACHE = [*TEMPLATES, *COMMUNICATION]
    return _TEMPLATES_CACHE


def _template_map() -> dict[str, SandboxTemplate]:
    global _TEMPLATE_MAP_CACHE
    if _TEMPLATE_MAP_CACHE is None:
        _TEMPLATE_MAP_CACHE = {t.template_id: t for t in _load_templates()}
    return _TEMPLATE_MAP_CACHE


class SandboxService:
    """对话式沙盒：游客角色扮演 + 阶段推进 + 五维评估，全部由 LLM 驱动。"""

    def __init__(
        self,
        llm_client: LLMClient,
        store: SQLiteStore,
        plugin: Any | None = None,
        rng: random.Random | None = None,
    ) -> None:
        if plugin is None:
            from brain_of_cloud.plugins.tour_guide import TourGuidePlugin

            plugin = TourGuidePlugin()
        self._llm = llm_client
        self._store = store
        self._plugin = plugin
        self._rng = rng or random.Random()
        # ── v3 子智能体：游客动态生成 + 场景导演判定 ──
        from brain_of_cloud.services.customer_generator import CustomerGenerator
        from brain_of_cloud.services.scene_director import SceneDirectorAgent

        self._customer_gen = CustomerGenerator(llm_client)
        self._director = SceneDirectorAgent(llm_client)

    # ── 模板 ──

    def list_templates(self, mode: str | None = None) -> list[dict[str, Any]]:
        templates = _load_templates() if mode is None else [t for t in _load_templates() if t.mode == mode]
        return [
            {
                "template_id": t.template_id,
                "mode": t.mode,
                "requires": FULLFLOW_PREREQ.get(t.template_id, []),
                "title": t.title,
                "location": t.location,
                "task": t.task,
                "difficulty": t.difficulty,
                "category": t.category,
                "opening": t.opening,
                "stage_titles": [s.title for s in t.stages],
                "stage_count": len(t.stages),
            }
            for t in templates
        ]

    def get_template(self, template_id: str) -> SandboxTemplate:
        try:
            return _template_map()[template_id]
        except KeyError as exc:
            raise SandboxError(f"未知场景模板: {template_id}") from exc

    # ── 会话 ──

    def _generate_customer(self, template: SandboxTemplate, lang: str | None = None, trace_cb=None) -> CustomerProfile:
        """v3 游客动态生成：LLM 按模板+均匀随机年龄段生成多维人设。

        lang 非空时（语音/外语训练），国籍锁定为该语言母语国家（见 customer_generator）。
        生成失败（LLM 不可用/解析失败）→ 兜底模板游客池随机选一位（兼容旧行为）。
        """
        try:
            data = self._customer_gen.generate(template, self._rng, lang=lang)
            if data and data.get("name"):
                trace_event(trace_cb, "customer_generator", "生成游客背景", "done", "游客背景与隐藏诉求已就绪", step="collaboration")
                return _customer_from_dict(data)
        except Exception:
            pass
        trace_event(trace_cb, "customer_generator", "生成游客背景", "failed", "生成暂不可用，已采用场景内置游客", step="collaboration")
        pool = template.customer_pool
        if lang:
            from dataclasses import replace

            from brain_of_cloud.services.language_profiles import country_for_language

            country = country_for_language(lang, self._rng)
            match = next((c for c in pool if c.nationality == country), None)
            if match is not None:
                return match
            base = self._rng.choice(pool)
            try:
                return replace(base, nationality=country)
            except Exception:
                return base
        return self._rng.choice(pool)

    def start_session(
        self,
        user_id: str,
        template_id: str,
        mode: str | None = None,
        language: str | None = None,
        voice: str | None = None,
        trace_cb: Callable[[dict], None] | None = None,
    ) -> dict[str, Any]:
        template = self.get_template(template_id)
        trace_event(trace_cb, "system", "准备实战场景", "done", step="planning")
        trace_event(trace_cb, "system", "确定实战分工", "done", step="dispatch", event="dispatch", round=1,
                    agents=["customer_generator", "customer_simulator"], tools=["start_session"])
        trace_event(trace_cb, "customer_generator", "生成游客背景", step="collaboration")
        # v3：游客动态生成（多维人设，年龄均匀分布）；LLM 失败时兜底模板游客池
        # 语音/外语训练：language 决定游客国籍（customer_generator 约束），voice 由语言+人设性别决定
        customer = self._generate_customer(template, lang=language, trace_cb=trace_cb)
        if language and not voice:
            from brain_of_cloud.services.language_profiles import pick_voice

            voice = pick_voice(language, getattr(customer, "gender", "") or "")

        session_id = f"sb_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "mode": template.mode,
            "template_id": template.template_id,
            "customer": _customer_dict(customer),
            "state": {
                "stage": 0,
                "stage_turns": 0,
                "messages": [],
                "scene_complete": False,
                # 语音/外语训练：语言码 + 音色（存 state JSON，避免动表结构）
                "voice_lang": (language or ""),
                "voice_name": (voice or ""),
                # 游客心理状态机（完整情景模拟：信任/情绪/疑虑/诉求流露随对话演变）
                "customer_state": {
                    "trust": self._rng.randint(50, 70),
                    "mood": "一般",
                    "concerns": [],
                    "hidden_revealed": False,
                },
                "tension_count": 0,      # 连续不满轮数（触发剧情压力事件）
                "tension_event": False,  # 剧情压力事件激活中（投诉/威胁离团）
            },
            "status": "active",
            "score": None,
            "dims": None,
            "feedback": None,
            "created_at": now,
            "ended_at": None,
        }
        self._store.save_sandbox_session(session)

        # 游客开场白：一次 LLM 调用；失败则用模板开场兜底
        trace_event(trace_cb, "customer_simulator", "游客准备开场", step="collaboration")
        opening_reply = self._customer_opening(template, customer, trace_cb=trace_cb)
        session["state"]["messages"].append(
            {"role": "customer", "content": opening_reply}
        )
        session["state"]["stage_turns"] = 0
        self._store.save_sandbox_session(session)
        trace_event(trace_cb, "system", "场景已准备好", "done", step="delivery")
        return self.get_session(session_id)

    def _customer_opening(self, template: SandboxTemplate, customer: CustomerProfile, trace_cb=None) -> str:
        fallback = f"{template.opening}（{customer.name}看着你，等你开口。）"
        try:
            initial_state = {"trust": self._rng.randint(50, 70), "mood": "一般",
                             "concerns": [], "hidden_revealed": False}
            resp = self._llm.generate(
                _customer_system_v2(template, customer, initial_state),
                (
                    "你刚抵达场景。请以游客身份开口说第一句话，自然引出当下处境"
                    "（可以说一句自己的疑问、期待或情绪）。"
                    "只输出 JSON：{\"reply\": \"...\", \"mood\": \"一般\"}。"
                ),
                temperature=0.9,
                max_tokens=256,
                response_format={"type": "json_object"},
            )
            parsed = _parse_json(resp.content)
            reply = parsed.get("reply") or parsed.get("content")
            trace_event(trace_cb, "customer_simulator", "游客准备开场", "done", step="collaboration")
            return reply if reply else fallback
        except Exception:
            trace_event(trace_cb, "customer_simulator", "游客准备开场", "failed", "已采用场景开场白", step="collaboration")
            return fallback

    # ── 对话 ──

    def send_message(self, session_id: str, user_text: str, trace_cb: Callable[[dict], None] | None = None) -> dict[str, Any]:
        session = self._require_active(session_id)
        trace_event(trace_cb, "system", "读取当前场景与对话", "done", step="planning")
        trace_event(trace_cb, "system", "确定本轮互动分工", "done", step="dispatch", event="dispatch", round=1,
                    agents=["customer_simulator", "scene_director"], tools=["send_message"])
        trace_event(trace_cb, "customer_simulator", "回应学员，更新游客情绪", step="collaboration")
        template = self.get_template(session["template_id"])
        customer = _customer_from_dict(session["customer"])
        state = session["state"]
        stage_idx = state["stage"]
        stage = template.stages[stage_idx]
        cs = state.setdefault(
            "customer_state",
            {"trust": 60, "mood": "一般", "concerns": [], "hidden_revealed": False},
        )
        recap = _build_recap(state["messages"])

        # 组装含心理状态与记忆的游客 prompt（完整情景模拟）
        system = _customer_system_v2(template, customer, cs, recap)
        user_prompt = (
            f"【你的记忆】\n{recap}\n"
            f"（最新）导游说：{user_text}\n\n"
            f"【当前阶段】{stage.title}：{stage.objective}\n"
            "请以游客身份回复（JSON）。"
        )

        try:
            resp = self._llm.generate(
                system,
                user_prompt,
                temperature=0.9,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            parsed = _parse_json(resp.content)
            reply = parsed.get("reply") or "(游客沉默片刻)"
            mood = parsed.get("mood", "一般")
            advanced = bool(parsed.get("advanced"))
            trust_delta = _to_int(parsed.get("trust_delta"), 0, -30, 30)
            reaction = str(parsed.get("reaction") or "").strip()
            hidden_revealed = bool(parsed.get("hidden_revealed"))
            trace_event(trace_cb, "customer_simulator", "游客已回应", "done", step="collaboration")
        except Exception:
            trace_event(trace_cb, "customer_simulator", "游客回应暂不可用", "failed", "保持当前场景，稍后可继续互动", step="collaboration")
            reply, mood, advanced = "(游客沉默片刻)", "一般", False
            trust_delta, reaction, hidden_revealed = 0, "", False

        # 写入本轮到消息列表
        state["messages"].append({"role": "guide", "content": user_text})
        state["messages"].append({"role": "customer", "content": reply, "mood": mood})
        state["stage_turns"] += 1

        # ── 游客心理状态更新 ──
        cs["trust"] = max(0, min(100, cs["trust"] + trust_delta))
        cs["mood"] = mood
        if reaction:
            concerns = [c for c in cs.get("concerns", []) if c != reaction]
            concerns.append(reaction)
            cs["concerns"] = concerns[-3:]
        if hidden_revealed:
            cs["hidden_revealed"] = True
        # 连续不满计数（触发剧情压力事件）
        if trust_delta <= 0 and mood in ("不满", "愤怒"):
            state["tension_count"] = state.get("tension_count", 0) + 1
        else:
            state["tension_count"] = 0

        # ── 剧情推进（v3：场景导演智能体判定场景是否结束/推进）──
        # 导演判定优先：fail（搞砸了）→ complete（达成目标）→ advance（阶段推进）；
        # 导演返回 continue 或判定失败时，兜底沿用原逻辑（advanced 判定 + 压力事件 + 防呆上限）。
        goal_met = advanced and state["stage_turns"] >= stage.min_turns
        stage_tip = None
        moved = False
        scene_outcome = None
        scene_fail_reason = None
        director_action = None
        director_reason = ""
        trace_event(trace_cb, "scene_director", "判断目标与阶段推进", step="collaboration")
        try:
            d = self._director.decide(
                template, stage_idx, customer, cs,
                _transcript(state["messages"]), state["stage_turns"],
            )
            director_action = d.action
            director_reason = d.reason or ""
            trace_event(trace_cb, "scene_director", "判断目标与阶段推进", "done", director_reason, step="collaboration")
        except Exception:
            trace_event(trace_cb, "scene_director", "判断目标与阶段推进", "failed", "采用场景规则判断", step="collaboration")
            director_action = None

        if director_action == "fail":
            # 搞砸了：信任崩塌/学员严重失误 → 场景失败结束
            state["scene_complete"] = True
            state["scene_outcome"] = "failed"
            state["scene_fail_reason"] = director_reason or "游客信任崩塌，场景失败。"
            moved = True
            stage_tip = {
                "type": "fail",
                "stage": stage_idx,
                "title": stage.title,
                "message": f"场景失败：{state['scene_fail_reason']}",
                "scene_complete": True,
                "scene_outcome": "failed",
            }
        elif state.get("tension_event"):
            # 压力事件中：游客信任回升到 40 以上才算化解 → 解除事件，回到原阶段
            if cs["trust"] >= 40:
                state["tension_event"] = False
                state["tension_count"] = 0
                stage_tip = {
                    "type": "tension_resolved",
                    "stage": stage_idx,
                    "title": stage.title,
                    "message": "游客的情绪被你安抚下来了，他愿意继续配合。",
                }
            else:
                stage_tip = {
                    "type": "tension",
                    "stage": stage_idx,
                    "title": stage.title,
                    "message": (
                        "游客情绪仍很激动（信任度 " + str(cs["trust"]) + "）。"
                        "你必须先安抚他：道歉、给承诺、给实际补偿，"
                        "否则本阶段无法推进，他可能投诉甚至离团。"
                    ),
                }
        elif director_action == "complete":
            state["scene_complete"] = True
            state["scene_outcome"] = "success"
            moved = True
            stage_tip = {
                "type": "complete", "stage": stage_idx, "title": stage.title,
                "message": director_reason or "所有阶段目标达成，场景圆满结束。",
                "scene_complete": True, "scene_outcome": "success",
            }
        elif director_action == "advance":
            if stage_idx < len(template.stages) - 1:
                state["stage"] += 1
                state["stage_turns"] = 0
                moved = True
                next_stage = template.stages[state["stage"]]
                stage_tip = {
                    "type": "stage",
                    "stage": state["stage"],
                    "title": next_stage.title,
                    "objective": next_stage.objective,
                    "guide_hint": next_stage.guide_hint,
                    "message": director_reason or "",
                }
            else:
                state["scene_complete"] = True
                state["scene_outcome"] = "success"
                moved = True
                stage_tip = {
                    "type": "complete", "stage": stage_idx, "title": stage.title,
                    "message": director_reason or "所有阶段目标达成，场景圆满结束。",
                    "scene_complete": True, "scene_outcome": "success",
                }
        elif goal_met and stage_idx < len(template.stages) - 1:
            state["stage"] += 1
            state["stage_turns"] = 0
            moved = True
            next_stage = template.stages[state["stage"]]
            stage_tip = {
                "type": "stage",
                "stage": state["stage"],
                "title": next_stage.title,
                "objective": next_stage.objective,
                "guide_hint": next_stage.guide_hint,
            }
        elif goal_met and stage_idx == len(template.stages) - 1:
            state["scene_complete"] = True
            state["scene_outcome"] = "success"
            moved = True
            stage_tip = {"type": "complete", "stage": stage_idx, "title": stage.title, "scene_complete": True}
        elif cs["trust"] < 30 and state.get("tension_count", 0) >= 2:
            # 剧情压力事件：游客信任崩塌 → 投诉/威胁离团（学员必须化解）
            state["tension_event"] = True
            stage_tip = {
                "type": "tension",
                "stage": stage_idx,
                "title": stage.title,
                "message": (
                    "游客脸色已经很难看（信任度 " + str(cs["trust"]) + "）："
                    "「我要找你们旅行社投诉！」如果你不能马上安抚他，"
                    "这一局很难继续带下去了。"
                ),
            }
        elif state["stage_turns"] >= stage.max_turns:
            # 防呆上限：剧情卡住太久，强制收束本阶段（带提示，非固定轮数）
            if stage_idx < len(template.stages) - 1:
                state["stage"] += 1
                state["stage_turns"] = 0
                moved = True
                next_stage = template.stages[state["stage"]]
                stage_tip = {
                    "type": "timeout",
                    "stage": state["stage"],
                    "title": next_stage.title,
                    "objective": next_stage.objective,
                    "guide_hint": next_stage.guide_hint,
                    "message": "游客已经明显不耐烦，本阶段话题聊得够久了，自动进入下一阶段。",
                }
            else:
                state["scene_complete"] = True
                state["scene_outcome"] = "success"
                moved = True
                stage_tip = {"type": "complete", "stage": stage_idx, "title": stage.title, "scene_complete": True}

        self._store.save_sandbox_session(session)

        trace_event(trace_cb, "system", "游客回应与场景状态已更新", "done", step="delivery")
        return {
            "reply": reply,
            "mood": mood,
            "trust": cs["trust"],
            "hidden_revealed": cs["hidden_revealed"],
            "stage": state["stage"],
            "stage_total": len(template.stages),
            "stage_title": template.stages[state["stage"]].title,
            "stage_advanced": moved,
            "stage_tip": stage_tip,
            "tension": bool(state.get("tension_event")),
            "scene_complete": state["scene_complete"],
            "scene_outcome": state.get("scene_outcome"),
            "scene_fail_reason": state.get("scene_fail_reason"),
        }

    # ── 评估 ──

    def end_session(self, session_id: str, user_id: str | None = None, trace_cb: Callable[[dict], None] | None = None) -> dict[str, Any]:
        session = self._store.get_sandbox_session(session_id)
        if session is None:
            raise SandboxError(f"未知沙盒会话: {session_id}")
        if session["status"] == "ended":
            # 幂等：已结束直接返回既有评估结果
            return self.get_session(session_id)
        template = self.get_template(session["template_id"])
        customer = _customer_from_dict(session["customer"])
        transcript = _transcript(session["state"]["messages"])
        trace_event(trace_cb, "system", "整理本场实战记录", "done", step="planning")
        trace_event(trace_cb, "system", "确定复盘分工", "done", step="dispatch", event="dispatch", round=1,
                    agents=["sandbox_evaluator"], tools=["end_session"])
        trace_event(trace_cb, "sandbox_evaluator", "五维评分与复盘", step="collaboration")
        if not transcript:
            raise SandboxError("对话为空，无法评估")

        stage_lines = "\n".join(
            f"阶段{i + 1}·{s.title}：{s.objective}" for i, s in enumerate(template.stages)
        )
        goals_line = "、".join(f"{d}(权重{w})" for d, w in template.goals)
        cs = session["state"].get("customer_state", {})
        trust_now = int(cs.get("trust", 60))
        trust_path = _trust_path(session["state"].get("messages", []))
        revealed_note = "已流露并（若）被察觉" if cs.get("hidden_revealed") else "始终未流露"
        tension_note = "全程出现情绪对抗/投诉威胁" if session["state"].get("tension_event") or session["state"].get("tension_count", 0) >= 2 else "无明显冲突"
        # v3：场景结局（导演判定）注入评估，让评估与真实结果挂钩
        outcome = session["state"].get("scene_outcome")
        if outcome == "success":
            outcome_note = "场景结局：圆满达成（所有阶段目标完成，游客满意）"
        elif outcome == "failed":
            outcome_note = (
                "场景结局：失败（搞砸了）——" +
                str(session["state"].get("scene_fail_reason") or "游客信任崩塌或学员严重失误")
            )
        else:
            outcome_note = "场景结局：手动结束（未完成全部阶段）"
        stage_reached = session["state"].get("stage", 0) + 1
        outcome_note += f"；推进到第 {stage_reached}/{len(template.stages)} 阶段"

        try:
            resp = self._llm.generate(
                EVALUATOR_SYSTEM_PROMPT,
                (
                    f"【场景】{template.title}\n地点：{template.location}\n任务：{template.task}\n"
                    f"【游客】{customer.name}（{customer.nationality}，{customer.age}岁）\n"
                    f"性格：{customer.personality}；偏好：{customer.preferences}\n"
                    f"说话特点：{customer.quirks}\n隐藏诉求：{customer.hidden}\n"
                    f"游客信任度：{trust_now}/100（轨迹：{' → '.join(trust_path) or '无'}）\n"
                    f"隐藏诉求流露：{revealed_note}；冲突情况：{tension_note}\n"
                    f"{outcome_note}\n\n"
                    f"【带团阶段】\n{stage_lines}\n\n"
                    f"【评估侧重】{goals_line}\n\n"
                    f"【完整对话转写】\n{transcript}\n\n"
                    "请给出评估（JSON）。"
                ),
                temperature=0.4,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            evaluation = _parse_json(resp.content)
            trace_event(trace_cb, "sandbox_evaluator", "五维评分与复盘", "done", step="collaboration")
        except Exception:
            trace_event(trace_cb, "sandbox_evaluator", "五维评分与复盘", "failed", "评估生成暂不可用，本次报告包含重试提示", step="collaboration")
            evaluation = {
                "total": 60,
                "dims": {d: 3 for d in FIVE_DIMS},
                "strengths": ["完成了一次完整的模拟带团"],
                "weaknesses": ["评估生成失败，请重试一次"],
                "suggestions": ["重新进行一轮沙盒模拟以获得有效反馈"],
                "skill_keywords": ["导游服务规范"],
            }

        evaluation = _normalize_evaluation(evaluation)

        # 关联知识库技能点
        recommended_skills = self._search_skills(evaluation.get("skill_keywords", []))

        now = datetime.now(timezone.utc).isoformat()
        session["status"] = "ended"
        session["score"] = evaluation["total"]
        session["dims"] = evaluation["dims"]
        session["feedback"] = {
            "strengths": evaluation["strengths"],
            "weaknesses": evaluation["weaknesses"],
            "suggestions": evaluation["suggestions"],
            "skill_keywords": evaluation["skill_keywords"],
            "recommended_skills": recommended_skills,
            "culture_bridge": evaluation.get("culture_bridge"),
        }
        session["ended_at"] = now
        self._store.save_sandbox_session(session)

        # 沙盒评分 → 掌握度评估（kind=sandbox），让入境域 40/10/50 权重真正生效
        self._write_sandbox_mastery_assessments(session, template, evaluation)

        # 落为学习中心报告资产
        self._create_report_asset(session, template, evaluation, recommended_skills)
        trace_event(trace_cb, "system", "评分与报告已保存", "done", step="delivery")

        return self.get_session(session_id)

    def _write_sandbox_mastery_assessments(
        self,
        session: dict[str, Any],
        template: SandboxTemplate,
        evaluation: dict[str, Any],
    ) -> None:
        """沙盒结束 → 按本场景阶段知识点写入 sandbox 掌握度评估。

        让「入境游实战能力域」的沙盒 50%（及普通域 0% 权重之外的沙盒分）真正参与
        主客观综合掌握度（mastery_assessments kind=sandbox）。
        """
        uid = session.get("user_id")
        if not uid:
            return
        try:
            from brain_of_cloud.services.mastery import MasteryService

            ms = MasteryService(self._plugin, self._store)
        except Exception:
            return
        try:
            score = max(0.0, min(100.0, float(evaluation.get("total") or 0)))
        except (TypeError, ValueError):
            score = 0.0
        seen: list[str] = []
        for stage in template.stages:
            for kw in (getattr(stage, "kb_keywords", None) or []):
                try:
                    evs = self._plugin.search(query=kw, top_k=1)
                except Exception:
                    evs = []
                for e in evs or []:
                    kp = str(getattr(e, "chunk_id", "") or "")
                    if kp and kp not in seen:
                        seen.append(kp)
                        try:
                            ms.assess(uid, kp, "sandbox", score, "沙盒实战评分")
                        except Exception:
                            pass
                    if len(seen) >= 10:
                        break
                if len(seen) >= 10:
                    break
            if len(seen) >= 10:
                break

    def _search_skills(self, keywords: list[str]) -> list[dict[str, str]]:
        seen: set[str] = set()
        skills: list[dict[str, str]] = []
        for keyword in keywords:
            try:
                evidence = self._plugin.search(query=keyword, top_k=2)
            except Exception:
                continue
            for e in evidence:
                if e.chunk_id in seen:
                    continue
                try:
                    skill = self._plugin.get_skill(e.chunk_id)
                except Exception:
                    skill = None
                if skill is None:
                    continue
                seen.add(e.chunk_id)
                skills.append(
                    {
                        "id": skill.id,
                        "title": skill.title,
                        "content": (skill.content or "")[:120],
                        "source": getattr(e, "source", ""),
                    }
                )
                if len(skills) >= 5:
                    break
            if len(skills) >= 5:
                break
        return skills

    def _create_report_asset(
        self,
        session: dict[str, Any],
        template: SandboxTemplate,
        evaluation: dict[str, Any],
        recommended_skills: list[dict[str, str]],
    ) -> None:
        from brain_of_cloud.domain.models import Asset, AssetType

        dim_lines = "\n".join(
            f"- {name}: {'★' * score}{'☆' * (5 - score)} ({score}/5)"
            for name, score in evaluation["dims"].items()
        )
        bridge_section = ""
        cb = evaluation.get("culture_bridge")
        if cb:
            cb_score = int(cb.get("score", 0))
            bridge_section = (
                "\n### 文化桥 · 附加观察（不计入总分）\n"
                f"- 评分：{'★' * cb_score}{'☆' * (5 - cb_score)}（{cb_score}/5）\n"
                f"- 说明：{cb.get('summary') or '无'}\n"
            )
        skill_lines = "\n".join(
            f"- {s['title']}" for s in recommended_skills
        ) or "- 暂无关联技能点"
        content = (
            f"## 沙盒模拟评估 · {template.title}\n\n"
            f"- 游客：{session['customer']['name']}（{session['customer']['nationality']}）\n"
            f"- 综合得分：**{evaluation['total']} / 100**\n\n"
            f"### 五维评分\n{dim_lines}\n\n{bridge_section}"
            f"### 亮点\n" + "\n".join(f"- {s}" for s in evaluation["strengths"]) + "\n\n"
            f"### 不足\n" + "\n".join(f"- {w}" for w in evaluation["weaknesses"]) + "\n\n"
            f"### 提升建议\n" + "\n".join(f"- {s}" for s in evaluation["suggestions"]) + "\n\n"
            f"### 关联技能点（建议复习）\n{skill_lines}"
        )
        asset = Asset(
            asset_id=f"asset_{uuid.uuid4().hex[:16]}",
            user_id=session["user_id"],
            session_id=session["session_id"],
            title=f"沙盒评估 · {template.title}",
            asset_type=AssetType.REPORT,
            content=content,
            source_tool="sandbox",
        )
        self._store.save_asset(asset)

    # ── 读取 ──

    def append_voice_messages(
        self,
        session_id: str,
        user_id: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """语音会话：把实时语音产生的台词（导游/游客）追加进会话消息，供结算评估。

        不触发游客 Agent（实时语音游客由 Qwen Realtime 承担），只做记录。
        """
        session = self._require_active(session_id)
        if user_id and session.get("user_id") and user_id != session.get("user_id"):
            raise SandboxError("user_id 与会话不匹配")
        state = session["state"]
        added = 0
        for m in messages or []:
            role = str(m.get("role", "") or "")
            content = str(m.get("content", "") or "").strip()
            if role not in ("guide", "customer") or not content:
                continue
            state["messages"].append({"role": role, "content": content})
            if role == "guide":
                state["stage_turns"] = int(state.get("stage_turns", 0)) + 1
            added += 1
        if added:
            self._store.save_sandbox_session(session)
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self._store.get_sandbox_session(session_id)
        if session is None:
            raise SandboxError(f"未知沙盒会话: {session_id}")
        template = self.get_template(session["template_id"])
        stage_idx = session["state"]["stage"]
        stage = template.stages[min(stage_idx, len(template.stages) - 1)]
        out = dict(session)
        out["language"] = str(session["state"].get("voice_lang") or "")
        out["voice"] = str(session["state"].get("voice_name") or "")
        out["customer"] = _public_customer(session["customer"])
        out["messages"] = session["state"]["messages"]
        out["scene_complete"] = session["state"]["scene_complete"]
        out["scene_outcome"] = session["state"].get("scene_outcome")
        out["scene_fail_reason"] = session["state"].get("scene_fail_reason")
        out["template"] = {
            "template_id": template.template_id,
            "mode": template.mode,
            "title": template.title,
            "location": template.location,
            "task": template.task,
            "difficulty": template.difficulty,
            "category": template.category,
            "opening": template.opening,
        }
        out["stage"] = {
            "index": stage_idx,
            "total": len(template.stages),
            "title": stage.title,
            "objective": stage.objective,
            "guide_hint": stage.guide_hint,
            "kb_keywords": stage.kb_keywords,
        }
        # 游客心理状态（公开子集：供前端游客心情条展示）
        cs = session["state"].get("customer_state", {})
        out["customer_state"] = {
            "trust": int(cs.get("trust", 60)),
            "mood": cs.get("mood", "一般"),
            "hidden_revealed": bool(cs.get("hidden_revealed")),
            "tension": bool(session["state"].get("tension_event")),
        }
        out.pop("state", None)
        return out

    def list_user_records(self, user_id: str) -> list[dict[str, Any]]:
        records = self._store.list_sandbox_records(user_id)
        out = []
        for r in records:
            try:
                template = self.get_template(r["template_id"])
                title = template.title
            except SandboxError:
                title = r["template_id"]
            out.append(
                {
                    "session_id": r["session_id"],
                    "mode": r["mode"],
                    "template_id": r["template_id"],
                    "title": title,
                    "score": r["score"],
                    "dims": r["dims"],
                    "ended_at": r["ended_at"],
                }
            )
        return out

    def _require_active(self, session_id: str) -> dict[str, Any]:
        session = self._store.get_sandbox_session(session_id)
        if session is None:
            raise SandboxError(f"未知沙盒会话: {session_id}")
        if session["status"] != "active":
            raise SandboxError(f"沙盒会话已结束: {session_id}")
        return session


# ── 工具函数 ──

def _customer_system_v2(
    template: SandboxTemplate,
    customer: CustomerProfile,
    customer_state: dict[str, Any],
    recap: str = "",
) -> str:
    """组装游客 system prompt：人设 + 当前阶段 + 心理状态 + 连续记忆。"""
    stage = template.stages[0]
    trust = int(customer_state.get("trust", 60))
    mood = customer_state.get("mood", "一般")
    concerns = customer_state.get("concerns", [])
    revealed = "已主动说出隐藏诉求" if customer_state.get("hidden_revealed") else "尚未透露"
    concerns_text = "；".join(str(c) for c in concerns[-3:]) or "暂无"
    base = CUSTOMER_SYSTEM_PROMPT.format(
        name=customer.name,
        country=customer.nationality,
        age=customer.age,
        personality=customer.personality,
        preferences=customer.preferences,
        quirks=customer.quirks,
        hidden=customer.hidden,
        opening=template.opening,
        location=template.location,
        stage_title=stage.title,
        objective=stage.objective,
        situation=template.situation or "（你只是普通游客，正在正常游玩）",
        trust=trust,
        mood=mood,
        concerns=concerns_text,
        revealed_note=revealed,
        recap=recap or "（刚开始接触，还没有什么特别经历）",
    )
    # v3：多维人设注入（职业/健康/消费/说话风格）——强化发言行为与个人属性相关性
    try:
        from brain_of_cloud.services.customer_generator import inject_profile_into_customer_prompt

        extra = inject_profile_into_customer_prompt(_customer_dict(customer))
        if extra:
            base = base.replace("【角色规则】", f"{extra}\n\n【角色规则】", 1)
    except Exception:
        pass
    return base


def _build_recap(messages: list[dict[str, Any]], keep: int = 6) -> str:
    """对话记忆摘要：保留最近 keep 条消息（游客的连续记忆来源）。"""
    if not messages:
        return ""
    lines = []
    for m in messages[-keep:]:
        role = "游客" if m.get("role") == "customer" else "导游"
        lines.append(f"{role}：{m['content'][:80]}")
    return "\n".join(lines)


def _to_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _trust_path(messages: list[dict[str, Any]]) -> list[str]:
    """从对话中提取游客情绪轨迹（评估上下文用）。"""
    path = []
    for m in messages:
        if m.get("role") == "customer" and m.get("mood"):
            path.append(str(m["mood"]))
    return path[-5:] or ["一般"]


def _customer_system(template: SandboxTemplate, customer: CustomerProfile) -> str:
    """旧版签名兼容（已废弃，保留引用安全）。"""
    stage = template.stages[0]
    return CUSTOMER_SYSTEM_PROMPT.format(
        name=customer.name,
        country=customer.nationality,
        age=customer.age,
        personality=customer.personality,
        preferences=customer.preferences,
        quirks=customer.quirks,
        hidden=customer.hidden,
        opening=template.opening,
        location=template.location,
        stage_title=stage.title,
        objective=stage.objective,
        situation=template.situation or "（你只是普通游客，正在正常游玩）",
        trust=60,
        mood="一般",
        concerns="暂无",
        revealed_note="尚未透露",
        recap="（刚开始接触，还没有什么特别经历）",
    )


def _customer_dict(customer: CustomerProfile) -> dict[str, str]:
    return {
        "name": customer.name,
        "nationality": customer.nationality,
        "age": customer.age,
        "personality": customer.personality,
        "preferences": customer.preferences,
        "quirks": customer.quirks,
        "hidden": customer.hidden,
        "gender": customer.gender,
        "occupation": customer.occupation,
        "health": customer.health,
        "consumption": customer.consumption,
        "speech_style": customer.speech_style,
    }


def _customer_from_dict(customer: dict[str, str]) -> CustomerProfile:
    return CustomerProfile(
        name=customer.get("name", "游客"),
        nationality=customer.get("nationality", "中国"),
        age=str(customer.get("age", "30")),
        personality=customer.get("personality", "随和"),
        preferences=customer.get("preferences", ""),
        quirks=customer.get("quirks", ""),
        hidden=customer.get("hidden", ""),
        gender=customer.get("gender", ""),
        occupation=customer.get("occupation", ""),
        health=customer.get("health", ""),
        consumption=customer.get("consumption", ""),
        speech_style=customer.get("speech_style", ""),
    )


def _public_customer(customer: dict[str, str]) -> dict[str, str]:
    """对外不暴露隐藏诉求（评估时内部使用）。"""
    return {k: v for k, v in customer.items() if k != "hidden"}


def _transcript(messages: list[dict[str, Any]]) -> str:
    lines = []
    for m in messages:
        role = "游客" if m.get("role") == "customer" else "导游"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def _parse_json(text: str) -> dict[str, Any]:
    """稳健解析 LLM 返回的 JSON：先整体 json.loads，再正则抽取对象。"""
    if not text:
        return {}
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            pass
    # 兜底：尝试提取 reply/content 字段
    reply = _extract_field(text, "reply") or _extract_field(text, "content")
    return {"reply": reply, "advanced": False} if reply else {}


def _extract_field(text: str, key: str) -> str | None:
    match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if match:
        return match.group(1).encode().decode("unicode_escape", errors="ignore")
    return None


def _normalize_evaluation(eval_data: dict[str, Any]) -> dict[str, Any]:
    dims = {}
    for dim in FIVE_DIMS:
        raw = eval_data.get("dims", {}).get(dim)
        try:
            score = int(float(raw))
        except (TypeError, ValueError):
            score = 3
        dims[dim] = max(1, min(5, score))

    try:
        total = int(float(eval_data.get("total", 60)))
    except (TypeError, ValueError):
        total = 60
    total = max(0, min(100, total))

    def _list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(x) for x in value if str(x).strip()][:4]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    # 文化桥：附加观察（不计入 total / 五维），仅用于报告
    culture_bridge = None
    cb_raw = eval_data.get("culture_bridge")
    if isinstance(cb_raw, dict):
        try:
            cb_score = int(float(cb_raw.get("score", 0)))
        except (TypeError, ValueError):
            cb_score = 0
        if 1 <= cb_score <= 5:
            culture_bridge = {
                "score": cb_score,
                "summary": str(cb_raw.get("summary") or "").strip()[:200],
            }

    return {
        "total": total,
        "dims": dims,
        "strengths": _list(eval_data.get("strengths")) or ["完成了一次完整的模拟带团"],
        "weaknesses": _list(eval_data.get("weaknesses")) or ["可再打磨细节"],
        "suggestions": _list(eval_data.get("suggestions")) or ["针对薄弱维度针对性复习"],
        "skill_keywords": _list(eval_data.get("skill_keywords")) or ["导游服务规范"],
        "culture_bridge": culture_bridge,
    }

