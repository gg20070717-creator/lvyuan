"""Orchestrator — 消息总线与工具执行中枢。
                                # ── 固定题（客观+简答）全答对 → 自动标记完成（前端弹完成去向卡），并让管家 finish_topic 收尾 ──
                                try:
                                    _tsF = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
                                    _tpcF = list(_tsF.get("topic_ids") or [])
                                    _doneF = self._training.correct_question_ids(self._current_user_id)
                                    _fullF = self._training.topic_question_pool(_tpcF)
                                    if _fullF and all(q.question_id in _doneF for q in _fullF):
                                        if not _tsF.get("topic_finished"):
                                            _tsF["topic_finished"] = True
                                            self._teaching.save(_tsF)
                                        conversation.append({
                                            "role": "system",
                                            "content": "本技能点固定题已全部完成，系统会自动弹出完成去向卡。请调用 finish_topic 做正式收尾，并向学员简要确认。",
                                        })
                                except Exception:
                                    pass

架构：管家 Concierge 通过函数调用自主决定调用哪些工具（无固定工作流）。
本模块负责：
- 会话历史加载/持久化（SQLite）
- 每用户记忆与画像注入（个性化）
- 工具执行（检索 / 生成 / 六帽审查 / 出题 / 判分 / 报告 / 计划 / 画像）
- 六帽审查未通过 → 驱动修订循环
"""

from __future__ import annotations

import contextvars
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

from brain_of_cloud.domain.models import (
    AgentId,
    AgentRun,
    AssetType,
    Evidence,
    Mention,
    Message,
    RunStatus,
    Task,
    TaskStatus,
    Visibility,
)
from brain_of_cloud.services.agents.base import AgentResult
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents import (
    BlackHatAgent,
    BlueHatAgent,
    GreenHatAgent,
    LearningPlannerAgent,
    ProfileAgent,
    RedHatAgent,
    RetrievalAgent,
    TextGeneratorAgent,
    TrainingAnalyzerAgent,
    WhiteHatAgent,
    YellowHatAgent,
)
from brain_of_cloud.services.agents.concierge import AgentResponse, ConciergeAgent
from brain_of_cloud.services.onboarding import IDENTITY_QUESTIONS as _IDQ
from brain_of_cloud.services.agents.essay_question import EssayQuestionAgent
from brain_of_cloud.services.assets import AssetService
from brain_of_cloud.services.agent_catalog import ALIASES, trace_event
from brain_of_cloud.services.context import ConversationContextManager
from brain_of_cloud.services.memory import UserMemoryService
from brain_of_cloud.services.teaching import TeachingStateService
from brain_of_cloud.services.training import TrainingService
from brain_of_cloud.services.web_search import WebSearchService
from brain_of_cloud.storage.sqlite import SQLiteStore
from brain_of_cloud.tools import ToolCall, ToolRegistry, ToolResult
from brain_of_cloud.tools.agent_tools import CONCIERGE_TOOLS


@dataclass(frozen=True)
class OrchestratorResult:
    task: Task
    input_message: Message
    response: str  # concierge's final text response to user
    tool_calls_made: list[str] = field(default_factory=list)  # tools that were called
    generated_content: str = ""  # only if generate_material was called
    review_verdict: str = ""  # only if review_material was called
    hat_details: dict[AgentId, AgentResult] | None = None
    rounds_used: int = 0
    assets: list[dict[str, object]] = field(default_factory=list)  # 本次生成的文件资产
    teaching: dict[str, object] | None = None  # 教学会话状态（主题/阶段/最近一题）


class Orchestrator:
    def __init__(
        self,
        store: SQLiteStore,
        plugin: InboundGuidePlugin | None = None,
        llm_client: LLMClient | None = None,
        max_review_rounds: int = 1,
    ) -> None:
        if llm_client is None:
            raise ValueError("Orchestrator requires an LLMClient.")
        self._store = store
        if plugin is None:
            from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
            plugin = TourGuidePlugin()
        self._plugin = plugin
        self._llm = llm_client
        self._max_review_rounds = max_review_rounds

        # Agents
        self._concierge = ConciergeAgent(llm_client)
        self._retrieval = RetrievalAgent(self._plugin, llm_client)
        self._text_generator = TextGeneratorAgent(llm_client)
        self._blue_hat = BlueHatAgent(llm_client)
        self._white_hat = WhiteHatAgent(llm_client)
        self._black_hat = BlackHatAgent(llm_client)
        self._green_hat = GreenHatAgent(llm_client)
        self._yellow_hat = YellowHatAgent(llm_client)
        self._red_hat = RedHatAgent(llm_client)
        self._training = TrainingService(self._plugin, store=self._store)
        self._teaching = TeachingStateService(self._store)
        self._profile = ProfileAgent(llm_client)
        self._analyzer = TrainingAnalyzerAgent(llm_client, self._training)
        self._essay_agent = EssayQuestionAgent(llm_client)
        self._planner = LearningPlannerAgent(llm_client)
        self._memory = UserMemoryService(self._store)
        self._assets = AssetService(self._store)
        # ── 会话上下文管理（T7：长对话摘要 + token 预算）──
        self._context_mgr = ConversationContextManager(llm_client)
        # ── 网络搜索（T13：知识检索第三来源，静默降级）──
        self._web_search = WebSearchService()
        # ── 知识技能树点亮：activate_skill 直接落库（支持知识树节点 id）──

        # Tool registry
        self._tools = ToolRegistry()
        self._register_tools()

        # ── 会话历史缓存（会话内容持久化于 SQLite，这里做内存缓存）──
        self._sessions: dict[str, list[dict[str, Any]]] = {}
        self._sessions_lock = threading.RLock()

        # 当前请求的用户上下文（contextvar — 每个请求线程独立，线程安全）
        self._user_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("orch_user_id", default="")
        self._session_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("orch_session_id", default="")
        # 实时多 Agent 轨迹回调（contextvar — 随请求线程注入，线程安全）
        self._trace_cb_ctx: contextvars.ContextVar[Callable[[dict], None] | None] = contextvars.ContextVar(
            "orch_trace_cb", default=None
        )

    @property
    def _current_user_id(self) -> str:
        return self._user_id_ctx.get()

    @property
    def _current_session_id(self) -> str:
        return self._session_id_ctx.get()

    def _register_tools(self) -> None:
        for td in CONCIERGE_TOOLS:
            handler = getattr(self, f"_handle_{td.name}", None)
            if handler:
                self._tools.register(td, handler)

    # ================= 工具处理器 =================

    _TOOL_AGENT_MAP = {
        "search_knowledge": AgentId.RETRIEVAL,
        "generate_material": AgentId.TEXT_GENERATOR,
        "review_material": AgentId.BLUE_HAT,
        "quiz_user": AgentId.TRAINING_ANALYZER,
        "submit_answer": AgentId.TRAINING_ANALYZER,
        "generate_essay_question": AgentId.ESSAY_QUESTION,
        "generate_report": AgentId.TRAINING_ANALYZER,
        "generate_plan": AgentId.LEARNING_PLANNER,
        "update_profile": AgentId.PROFILE,
        "activate_skill": AgentId.PROFILE,
        "finish_topic": AgentId.CONCIERGE,
        "ask_identity_question": AgentId.CONCIERGE,
        "submit_identity_answer": AgentId.CONCIERGE,
    }

    # 工具调用 → 实时轨迹元信息（agent 键 / 显示名 / 动作说明）
    _TOOL_TRACE = {
        "search_knowledge": ("retrieval", "知识检索", "检索知识库证据"),
        "set_teaching_topic": ("concierge", "司南管家", "锁定教学主题"),
        "activate_skill": ("profile", "画像师", "点亮技能节点"),
        "generate_material": ("draft", "内容起草", "起草学习材料"),
        "review_material": ("review", "六帽审查", "并行质量审查"),
        "quiz_user": ("trainer", "训练师", "抽取测验题"),
        "submit_answer": ("trainer", "训练师", "判分你的作答"),
        "generate_essay_question": ("essay", "简答出题", "生成进阶简答题"),
        "generate_report": ("analyzer", "学习分析师", "生成学习报告"),
        "generate_plan": ("planner", "计划师", "制定学习计划"),
        "update_profile": ("profile", "画像师", "更新学员画像"),
        "finish_topic": ("concierge", "司南管家", "收尾当前主题"),
        "ask_identity_question": ("concierge", "司南管家", "先验画像 · 身份题"),
        "submit_identity_answer": ("concierge", "司南管家", "先验画像 · 记录作答"),
    }

    # 六帽审查 → 实时轨迹（白/黑/绿/黄/红并行，蓝帽汇总）
    _HAT_TRACE = {
        AgentId.WHITE_HAT: ("white_hat", "白帽 · 事实", "核查事实与数据"),
        AgentId.BLACK_HAT: ("black_hat", "黑帽 · 批判", "排查逻辑漏洞"),
        AgentId.GREEN_HAT: ("green_hat", "绿帽 · 创意", "提出优化建议"),
        AgentId.YELLOW_HAT: ("yellow_hat", "黄帽 · 价值", "评估内容价值"),
        AgentId.RED_HAT: ("red_hat", "红帽 · 适配", "检查学员适配"),
    }

    def _emit_trace(
        self,
        agent: str,
        name: str,
        role: str,
        status: str = "working",
        detail: str = "",
        **meta,
    ) -> None:
        """上报一条实时 Agent 工作轨迹（前端「多智能体协同」面板直播用，基于真实执行轨迹）。"""
        cb = self._trace_cb_ctx.get()
        if cb is None:
            return
        try:
            trace_event(cb, agent, role, status, detail or "", **meta)
        except Exception:
            pass

    @staticmethod
    def _tool_work_note(tc: ToolCall) -> str:
        """从工具参数提炼「正在干什么」的说明，让同一 Agent 的不同次调用能区分。"""
        a = tc.arguments or {}
        name = tc.name
        q = str(a.get("query") or "").strip()
        if name == "search_knowledge" and q:
            return f"查询：{q[:60]}"
        req = str(a.get("request") or "").strip()
        if name == "generate_material" and req:
            return f"需求：{req[:60]}"
        if name == "set_teaching_topic":
            ids = a.get("knowledge_point_ids") or []
            return f"锁定主题（{len(ids)} 个技能点）" if ids else "锁定主题"
        if name == "quiz_user":
            ids = a.get("knowledge_point_ids") or []
            diff = str(a.get("difficulty") or "").strip()
            base = f"范围 {len(ids)} 个技能点" if ids else "随机摸底"
            return f"{base}（难度 {diff}）" if diff else base
        if name == "generate_essay_question":
            ids = a.get("knowledge_point_ids") or []
            return f"围绕 {len(ids)} 个技能点出简答题" if ids else "出进阶简答题"
        if name == "submit_answer":
            ans = str(a.get("answer") or "").strip()
            return f"作答：{ans[:40]}" if ans else ""
        if name == "update_profile":
            bg = str(a.get("background") or "").strip()
            return f"记录：{bg[:60]}" if bg else ""
        if name == "activate_skill":
            nid = str(a.get("node_id") or "")
            return f"点亮节点 {nid}" if nid else ""
        return ""

    def _identity_card(self, qid: str, prompt: str, options: list[str], step: int, total: int) -> None:
        try:
            ts = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            ts["stage"] = "practicing"
            ts["last_quiz"] = {
                "question_id": qid, "prompt": prompt, "options": list(options),
                "difficulty": "basic", "difficulty_level": 1, "type": "choice",
                "knowledge_point_title": f"先验画像 · 第 {step}/{total} 题",
                "progress": {"done": step - 1, "total": total, "exhausted": False},
            }
            self._teaching.save(ts)
        except Exception:
            pass

    def _handle_ask_identity_question(self) -> str:
        user = self._current_user_id
        try:
            if self._store.get_onboarding_profile(user):
                return json.dumps({"error": "identity_done", "message": "你已完成先验画像。"}, ensure_ascii=False)
            qa = self._store.get_onboarding_qa(user)
            step = int(qa.get("step") or 0)
            total = len(_IDQ)
            if step >= total:
                return json.dumps({"identity_done": True, "step": step, "total": total}, ensure_ascii=False)
            q = _IDQ[step]
            qid = f"onb_{q['id']}"
            opts = [o["label"] for o in q["options"]]
            self._identity_card(qid, q["question"], opts, step + 1, total)
            return json.dumps({
                "question_id": qid, "question": q["question"], "options": opts,
                "step": step + 1, "total": total, "identity_done": False,
            }, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _handle_submit_identity_answer(self, answer: str = "") -> str:
        user = self._current_user_id
        try:
            qa = self._store.get_onboarding_qa(user)
            step = int(qa.get("step") or 0)
            total = len(_IDQ)
            if step >= total:
                return json.dumps({"ok": True, "identity_done": True, "step": step, "total": total}, ensure_ascii=False)
            q = _IDQ[step]
            answers = dict(qa.get("answers") or {})
            chosen = None
            raw = (answer or "").strip()
            letter = raw.upper()
            if len(letter) == 1 and "A" <= letter <= chr(ord("A") + len(q["options"]) - 1):
                chosen = q["options"][ord(letter) - ord("A")]
            else:
                for o in q["options"]:
                    if raw == o["id"] or raw == o["label"]:
                        chosen = o
                        break
            if chosen is None:
                return json.dumps({"ok": False, "error": "bad_option", "message": "请选择卡片上的选项字母。"}, ensure_ascii=False)
            answers[q["id"]] = chosen["id"]
            step += 1
            self._store.save_onboarding_qa(user, step, answers)
            try:
                ts = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
                ts["stage"] = "feedback"
                ts["last_quiz"] = None
                self._teaching.save(ts)
            except Exception:
                pass
            done = step >= total
            return json.dumps({
                "ok": True, "identity_done": done, "step": step, "total": total,
                "question_id": f"onb_{q['id']}", "accepted": chosen["label"],
                "message": ("身份题已全部完成。" if done else "已记录，请继续下一题。"),
            }, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _handle_activate_skill(self, node_id: str = "", reason: str = "") -> str:
        """点亮知识技能树节点：管家确认学员掌握某技能点时直接落库（source=concierge）。

        接受知识树节点 id（book/part/chapter/section/skill），
        前端知识技能树按 node_id 读取点亮状态。
        """
        node_id = (node_id or "").strip()
        if not node_id:
            return json.dumps(
                {"error": "missing_node_id", "message": "请提供知识技能树节点 id（book/part/chapter/section/skill 的 id）"},
                ensure_ascii=False,
            )
        try:
            from uuid import uuid4
            self._store.save_skill_activation(
                activation_id=f"act_{self._current_user_id}_{node_id}_{uuid4().hex[:8]}",
                user_id=self._current_user_id,
                node_id=node_id,
                reason=reason or "",
                source="concierge",
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": "save_failed", "message": str(exc)}, ensure_ascii=False)
        return json.dumps({"ok": True, "node_id": node_id, "reason": reason}, ensure_ascii=False)

    def _agent_run_for_tool(
        self,
        task_id: str,
        message_id: str,
        tool_name: str,
    ) -> AgentRun | None:
        """工具调用 → 群组空间 agent_runs 审计记录（差距项 T5 接线）。"""
        agent_id = self._TOOL_AGENT_MAP.get(tool_name)
        if agent_id is None:
            return None
        try:
            return self._store.enqueue_agent_run(task_id, message_id, agent_id)
        except (KeyError, ValueError):
            return None

    def _handle_search_knowledge(self, query: str, knowledge_point_ids: list[str] | None = None) -> str:
        kp_ids = knowledge_point_ids or []
        result = self._retrieval.run(query=query, knowledge_point_ids=kp_ids, top_k=5)
        items = [
            {
                "chunk_id": e.chunk_id,
                "content": e.content[:400],  # 截断，控制上下文体积
                "source": e.source,
                "trust": e.trust_score,
                "title": self._skill_title(e.chunk_id),
                "knowledge_point_ids": list(e.knowledge_point_ids or [e.chunk_id]),
            }
            for e in result.evidence[:4]  # 控制证据条数
        ]

        # ── 教学主题自动锁定：首次检索（无主题）→ 用证据技能点开课 ──
        state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
        locked_topic_ids = []
        if not state.get("topic_ids") and state.get("stage") in ("goal_setting", "idle"):
            evidence_kp: list[str] = []
            for e in result.evidence[:4]:
                for kp in (e.knowledge_point_ids or [e.chunk_id]):
                    if kp and kp not in evidence_kp:
                        evidence_kp.append(kp)
            if evidence_kp:
                locked_topic_ids = evidence_kp[:3]
                state = self._teaching.set_topic(
                    self._current_session_id, self._current_user_id, locked_topic_ids,
                )

        return json.dumps(
            {
                "results": items,
                "count": len(items),
                "web_results": self._web_results_for(query, len(items)),  # T13：知识库证据不足时补充网络搜索
                "teaching": self._teaching_public(state),
            },
            ensure_ascii=False,
        )

    def _web_results_for(self, query: str, evidence_count: int) -> list[dict[str, object]]:
        """T13（D-2 第三来源）：知识库证据不足时用网络搜索补充（≤2 条，静默降级）。"""
        if evidence_count >= 3:
            return []
        try:
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("snippet", "")}
                for r in self._web_search.search(query, top_k=2)
            ]
        except Exception:
            return []

    def _handle_set_teaching_topic(self, knowledge_point_ids: list[str] | None = None) -> str:
        """显式锁定/切换教学主题（讲解新知识点、学员换主题时由管家调用）。"""
        kp_ids = knowledge_point_ids or []
        if not kp_ids:
            return json.dumps(
                {"error": "missing_knowledge_point_ids", "message": "请提供 knowledge_point_ids（可用 search_knowledge 结果里的技能点 ID）"},
                ensure_ascii=False,
            )
        state = self._teaching.set_topic(
            self._current_session_id, self._current_user_id, kp_ids,
        )
        return json.dumps(
            {
                "ok": True,
                "topic_titles": [self._skill_title(kp) for kp in kp_ids],
                "teaching": self._teaching_public(state),
            },
            ensure_ascii=False,
        )

    def _mastery_ctx_for(self, kp_ids: list[str], limit: int = 5) -> dict:
        """按当前技能点掌握度生成“目标难度档”注入上下文（供生成与红帽审查使用）。

        难度档与题库星级口径一致：avg>=0.85→综合版★4-5；>=0.70→进阶★3-4；
        >=0.55→基础★2-3；否则入门版★1-2。无作答数据→基础版兜底。
        """
        from brain_of_cloud.services.mastery import MasteryService
        kp_ids = list(kp_ids or [])[:limit]
        if not kp_ids:
            return {"kp_ids": [], "avg": None, "tier": "basic",
                    "tier_label": "基础版",
                    "prompt": "【学员掌握度】暂无锁定技能点，建议按基础版组织，内容须与参考证据一致。"}
        try:
            ms = MasteryService(self._plugin, self._store)
        except Exception:
            ms = None
        lines, tot, n = [], 0.0, 0
        for kid in kp_ids:
            try:
                d = ms.skill_mastery(self._current_user_id, kid) if ms else {}
                m = float(d.get("mastery") or 0)
            except Exception:
                continue
            obj = round(float(d.get("objective") or 0), 1)
            done = d.get("objective_done") or 0
            total = d.get("objective_total") or 0
            lines.append(f"- {self._skill_title(kid)}：综合掌握 {round(m,1)}%（客观 {obj}%，客观已答 {done}/{total} 题）")
            tot += m; n += 1
        if not lines:
            return {"kp_ids": kp_ids, "avg": None, "tier": "basic",
                    "tier_label": "基础版",
                    "prompt": "【学员掌握度】暂无作答数据，建议按基础版组织（先讲清概念、多给例子）。"}
        avg = tot / n
        # 与 competition_eval 校准后的推荐规则一致（<0.41→★1 / <0.535→★2 / <0.735→★3 / <0.88→★4 / 否则★5）
        _st = 1 if avg < 0.41 else 2 if avg < 0.535 else 3 if avg < 0.735 else 4 if avg < 0.88 else 5
        if _st >= 5:
            tier, label, star = "comprehensive", "综合版", "4-5"
        elif _st == 4:
            tier, label, star = "advanced", "进阶版", "3-4"
        elif _st == 3:
            tier, label, star = "basic", "基础版", "2-3"
        else:
            tier, label, star = "intro", "入门版", "1-2"
        rule = {
            "intro": "入门版：先讲清概念、名词和为什么，多用生活化比喻与最小例子，避免一步跳到多环节综合。",
            "basic": "基础版：概念+单场景步骤+常见坑，难度适中。",
            "advanced": "进阶版：多环节应用与条件判断，少铺垫、直奔要点。",
            "comprehensive": "综合版：跨知识点串联、决策与多场景综合，不再逐词解释基础概念。",
        }[tier]
        prompt = (
            f"【学员掌握度 → 目标难度档】当前相关技能点平均掌握 {round(avg,1)}%，"
            f"因此本次材料请按【{label}（约★{star}）】组织：{rule}。"
            f"内容深浅必须匹配该档位；同时仍需与参考证据完全一致、不编造。\n当前数据：\n" + "\n".join(lines)
        )
        return {"kp_ids": kp_ids, "avg": round(avg, 2), "tier": tier, "tier_label": label, "prompt": prompt}

    def _handle_generate_material(self, request: str, evidence: str = "{}") -> str:
        from brain_of_cloud.domain.models import Evidence as EvModel
        # 参数容错：模型偶发把 evidence 传成对象/数组而非 JSON 字符串（T16 鲁棒性）
        if isinstance(evidence, (dict, list)):
            evidence = json.dumps(evidence, ensure_ascii=False)
        try:
            ev_data = json.loads(evidence)
            items = ev_data.get("results", []) if isinstance(ev_data, dict) else ev_data
        except (json.JSONDecodeError, TypeError):
            items = []
        ev_list = [
            EvModel(
                chunk_id=e.get("chunk_id", f"ev_{i}"),  # 容错：管家重写证据时可能缺字段
                content=e.get("content", ""),
                source=e.get("source", ""),
                trust_score=e.get("trust", 0.8),
                knowledge_point_ids=e.get("knowledge_point_ids") or [],
            )
            for i, e in enumerate(items)
        ]
        retrieval = type("R", (), {"evidence": ev_list, "query": request})()
        msg = Message(
            message_id="gen", task_id="gen", from_agent=AgentId.CONCIERGE,
            content=request, lsn=1,
        )
        profile = self._store.get_learner_profile(self._current_user_id)
        _kp_ids = []
        for e in ev_list:
            _kp_ids.extend(e.knowledge_point_ids or [])
        if not _kp_ids:
            try:
                _ts = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
                _kp_ids = list(_ts.get("topic_ids") or [])
            except Exception:
                _kp_ids = []
        _mc = self._mastery_ctx_for(_kp_ids)
        content = self._text_generator.run(msg, retrieval, learner_profile=profile,
                                           mastery_context=_mc.get("prompt") or "")
        # 引用链：在材料末尾追加「参考来源」章节（差距项 T8）
        sources: list[str] = []
        for e in ev_list:
            src = (e.source or "").strip()
            if src and src not in sources:
                sources.append(src)
        if sources:
            refs = "\n".join(f"- {s}" for s in sources)
            content = f"{content}\n\n---\n**参考来源**：\n{refs}"
        asset = self._assets.create(
            user_id=self._current_user_id,
            session_id=self._current_session_id,
            title=self._asset_title(request),
            content=content,
            asset_type=self._infer_asset_type(request),
            source_tool="generate_material",
            evidence_ids=[e.chunk_id for e in ev_list],  # 结构化引用链（T14）
        )
        return json.dumps(
            {
                "content": content,
                "asset_id": asset.get("asset_id", ""),
                "title": asset.get("title", ""),
                "asset_type": asset.get("asset_type", "text"),
                "expected_difficulty": _mc.get("tier_label", ""),
                "mastery_avg": _mc.get("avg"),
            },
            ensure_ascii=False,
        )

    def _handle_review_material(self, content: str) -> str:
        hats = [
            (AgentId.WHITE_HAT, self._white_hat),
            (AgentId.BLACK_HAT, self._black_hat),
            (AgentId.GREEN_HAT, self._green_hat),
            (AgentId.YELLOW_HAT, self._yellow_hat),
            (AgentId.RED_HAT, self._red_hat),
        ]
        profile = self._store.get_learner_profile(self._current_user_id)
        # 红帽上下文适配：传入当前教学主题（红帽检查内容是否围绕正在教的主题）
        try:
            teaching = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            topic_ids = list(teaching.get("topic_ids") or [])
            teaching_context = "当前教学主题：" + "、".join(
                self._skill_title(kp) for kp in topic_ids
            ) if topic_ids else "（尚无锁定主题）"
            _mc_rev = self._mastery_ctx_for(topic_ids)
            if _mc_rev.get("prompt"):
                teaching_context += "\n\n" + _mc_rev["prompt"] +                     "\n（请在适配维度同时核查：本材料深浅是否匹配该目标难度档——太深则像在讲进阶内容，太浅则对掌握者无挑战。）"
        except Exception:
            teaching_context = ""
        hat_results: dict[AgentId, AgentResult] = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for aid, h in hats:
                hm = self._HAT_TRACE[aid]
                self._emit_trace(*hm, "working", step="collaboration")
                kwargs = dict(training_content=content, learner_profile=profile)
                if aid == AgentId.RED_HAT:
                    kwargs["teaching_context"] = teaching_context
                futures[executor.submit(h.run, **kwargs)] = aid
            for future in as_completed(futures):
                aid = futures[future]
                try:
                    hat_results[aid] = future.result()
                except Exception as exc:
                    hat_results[aid] = AgentResult(content=f"error: {exc}", passed=None)
                # ── 多 Agent 实时轨迹：逐帽完成即上报（真实并行时序，附思考摘要）──
                _hm = self._HAT_TRACE.get(aid)
                if _hm:
                    _hr = hat_results[aid]
                    _txt = str(getattr(_hr, "content", "") or "").strip().replace("\n", " ").strip()
                    _hd = ""
                    if _hr.passed is True:
                        _hd = f"判定通过：{_txt[:140]}" if _txt else "判定通过"
                    elif _hr.passed is False:
                        _hd = f"不通过：{_txt[:140]}" if _txt else "不通过"
                    elif _txt:
                        _hd = f"审查意见：{_txt[:140]}"
                    self._emit_trace(_hm[0], _hm[1], _hm[2],
                                     "failed" if _txt.startswith("error:") else "done",
                                     detail=_hd, step="collaboration")

        self._emit_trace("blue_hat", "蓝帽 · 裁决", "汇总五帽意见", "working", step="collaboration")
        review = self._blue_hat.coordinate(content, hat_results)
        verdict = "passed" if "合格" in review else "needs_revision"
        _blue_txt = str(review or "").strip().replace("\n", " ").strip()
        self._emit_trace(
            "blue_hat", "蓝帽 · 裁决", "汇总六帽 · 给出结论", "done",
            detail=(f"{'合格' if verdict == 'passed' else '需修改'}：{_blue_txt[:150]}" if _blue_txt
                    else ("审查通过" if verdict == "passed" else "需修订后再交付")),
        )

        hats_json = {
            aid.value: {"passed": r.passed, "summary": r.content[:200]}
            for aid, r in hat_results.items()
        }
        return json.dumps(
            {"review": review, "verdict": verdict, "hats": hats_json},
            ensure_ascii=False,
        )

    def _handle_quiz_user(
        self,
        knowledge_point_ids: list[str] | None = None,
        difficulty: str | None = None,
        random_mode: str | None = None,
    ) -> str:
        """出题（教学铁律 2 的硬校验落地）：

        - 必须绑定当前教学主题：knowledge_point_ids 为空时自动注入教学状态中的主题；
        - 仍无主题且学员未明确要求随机 → 拒绝出题（把管家逼回「先讲」）；
        - 难度自适应：按该主题掌握度 + 教学状态档位决策；
        - 排除本教学主题已出过的题目，避免重复。
        """
        state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
        kp_ids = list(knowledge_point_ids or [])
        random_mode = (random_mode or "").strip()

        if not kp_ids and state.get("topic_ids"):
            kp_ids = list(state["topic_ids"])
        if not kp_ids and random_mode != "explicit":
            return json.dumps(
                {
                    "error": "no_active_topic",
                    "message": "当前还没有确定教学主题。请先为学员讲解一个知识点并确认理解，再出题。"
                               "若学员明确要求随机摸底，才可设 random_mode='explicit'。",
                    "teaching": self._teaching_public(state),
                },
                ensure_ascii=False,
            )

        mastery_score = self._topic_mastery(self._current_user_id, kp_ids)
        decided = self._teaching.decide_difficulty(state, mastery_score)
        if difficulty:
            decided = difficulty
        # 随机摸底：优先未掌握/薄弱技能点，不纯随机
        if random_mode == "explicit" and not kp_ids:
            try:
                weak = self._training.get_mastery(self._current_user_id).weak_points
                kp_ids = weak[:3] or None
            except Exception:
                kp_ids = None

        exclude = set(state.get("quiz_history") or [])
        mastered = set(state.get("quiz_correct") or [])
        # 答对过的题（本会话 quiz_correct + 历史正确记录）永不再作为新题抽出，
        # 防止「答对后管家重锁主题把已出题历史清空 → 同一题又被抽出」的重复卡
        try:
            mastered |= self._training.correct_question_ids(self._current_user_id)
        except Exception:
            pass
        questions: list = []
        # ── 难度递进出题（赛题要求：难度曲线）：按 difficulty_level 从低到高固定顺序，
        #    低难度全部答对后自然轮到更高难度；不随机、不跳级。 ──
        if random_mode != "explicit":
            try:
                _ordered = self._training.next_progression_question(
                    kp_ids or None,
                    exclude_answered=exclude,
                    exclude_mastered=mastered,
                )
            except Exception:
                _ordered = None
            if _ordered is not None:
                questions = [_ordered]
        # 回退：学员明确要求随机摸底，或题库异常时的兜底（仍只出官方题库题、排除已出/已掌握）
        if not questions:
            try:
                questions = self._training.random_quiz(
                    n=1,
                    knowledge_point_ids=kp_ids or None,
                    difficulty=None if random_mode == "explicit" else decided,
                    exclude_answered=exclude | mastered,
                )
            except Exception:
                questions = []
            if not questions and kp_ids:
                try:
                    questions = self._training.random_quiz(
                        n=1,
                        knowledge_point_ids=kp_ids,
                        difficulty=None,
                        exclude_answered=exclude | mastered,
                    )
                except Exception:
                    questions = []
        # ── 主题选择题进度（进阶闭环：全部做完 → 引导管家推荐简答题）──
        try:
            progress = self._training.topic_quiz_progress(self._current_user_id, kp_ids)
        except Exception:
            progress = {"done": 0, "total": 0, "exhausted": False}
        if not questions:
            if progress.get("exhausted"):
                return json.dumps(
                    {
                        "question_id": "",
                        "type": "essay_ready",
                        "message": (
                            "当前教学主题的选择题已全部做完"
                            f"（已做 {progress.get('done', 0)}/{progress.get('total', 0)}）。"
                            "不要再出选择题。向学员推荐进阶内容（简答题），"
                            "学员同意后调 generate_essay_question 出简答题。"
                        ),
                        "progress": progress,
                        "teaching": self._teaching_public(state),
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "question_id": "",
                    "message": "该技能点题库暂无题目（后续补充题库后即可出题）。请不要自行编造题目，可先讲解或换一个知识点。",
                    "teaching": self._teaching_public(state),
                },
                ensure_ascii=False,
            )
        q = questions[0]
        question_info = {
            "question_id": q.question_id,
            "type": "choice",
            "prompt": q.prompt,
            "options": q.options,
            "difficulty": q.difficulty,
            "difficulty_level": getattr(q, "difficulty_level", None),
            "knowledge_point_title": self._skill_title(q.knowledge_point_id),
        }
        state = self._teaching.record_quiz(
            self._current_session_id, self._current_user_id,
            q.question_id, question_info=question_info, difficulty=decided,
        )
        return json.dumps(
            {
                "question_id": q.question_id,
                "type": "choice",
                "question": q.prompt,
                "difficulty": q.difficulty,
                "difficulty_level": getattr(q, "difficulty_level", None),
                "options": q.options,
                "source": q.source,
                "knowledge_point_title": question_info["knowledge_point_title"],
                "progress": progress,
                "teaching": self._teaching_public(state),
            },
            ensure_ascii=False,
        )

    def _handle_generate_essay_question(
        self,
        knowledge_point_ids: list[str] | None = None,
    ) -> str:
        """进阶简答题（题库固定题，非 AI 无限出）：从题库按难度升序抽下一道未掌握的简答。

        一个技能点的完整题量 = 客观题（选择/判断）+ 题库简答，全部答对才算通关（弹三选卡）；
        简答题也计入已答对集合，避免「AI 无限出题导致永远没有完成边界」。
        """
        state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
        kp_ids = list(knowledge_point_ids or [])
        if not kp_ids and state.get("topic_ids"):
            kp_ids = list(state["topic_ids"])
        if not kp_ids:
            return json.dumps(
                {
                    "error": "no_active_topic",
                    "message": "当前还没有确定教学主题。请先为学员讲解一个知识点并确认理解，且该主题选择题做完后，再出简答题。",
                    "teaching": self._teaching_public(state),
                },
                ensure_ascii=False,
            )

        try:
            _cids = self._training.correct_question_ids(self._current_user_id)
        except Exception:
            _cids = set()
        try:
            essay = self._training.next_essay_question(kp_ids, exclude_correct=_cids)
        except Exception:
            essay = None
        if essay is None:
            # 题库简答已全部做完（或该技能点没有简答）→ 固定题已通关
            return json.dumps(
                {
                    "error": "essay_done",
                    "type": "essay_done",
                    "message": "该主题题库简答题也已全部完成（固定题已通关）。不要再出题，向学员说明已全部完成。",
                    "teaching": self._teaching_public(state),
                },
                ensure_ascii=False,
            )

        topic_titles = [self._skill_title(kp) for kp in kp_ids]
        try:
            progress = self._training.topic_quiz_progress(self._current_user_id, kp_ids)
        except Exception:
            progress = {"done": 0, "total": 0, "exhausted": True}
        question_info = {
            "question_id": essay.question_id,
            "type": "essay",
            "prompt": essay.prompt,
            "rubric": essay.rubric or essay.answer_key or "",
            "difficulty": essay.difficulty or "advanced",
            "difficulty_level": essay.difficulty_level if essay.difficulty_level is not None
            else {"intro": 1, "basic": 2, "advanced": 3, "comprehensive": 4}.get(essay.difficulty or "advanced", 3),
            "knowledge_point_title": topic_titles[0] if topic_titles else "",
            "knowledge_point_id": essay.knowledge_point_id or (kp_ids[0] if kp_ids else ""),
        }
        state = self._teaching.record_quiz(
            self._current_session_id, self._current_user_id,
            essay.question_id, question_info=question_info,
            difficulty=question_info["difficulty"],
        )
        return json.dumps(
            {
                "question_id": essay.question_id,
                "type": "essay",
                "question": essay.prompt,
                "rubric": question_info["rubric"],
                "difficulty": question_info["difficulty"],
                "difficulty_level": question_info["difficulty_level"],
                "knowledge_point_title": question_info["knowledge_point_title"],
                "progress": progress,
                "teaching": self._teaching_public(state),
            },
            ensure_ascii=False,
        )

    def _handle_finish_topic(self) -> str:
        """管家宣告当前技能点题目全部完成 → 标记 topic_finished，前端据此弹出「完成去向卡」。"""
        state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
        if state.get("reteach_question_id"):
            return json.dumps(
                {"error": "reteach_lock", "message": "还有错题未重做完成，先让学员在卡片答对，再宣告完成。"},
                ensure_ascii=False,
            )
        state["topic_finished"] = True
        self._teaching.save(state)
        # ── 完成收尾 → 管家 AI 主观评分（0-100）并入库（kind=concierge）──
        ai_score = None
        try:
            from brain_of_cloud.services.mastery import MasteryService
            _ms = MasteryService(self._plugin, self._store)
            _kps = list(state.get("topic_ids") or [])
            _titles = [self._skill_title(k) for k in _kps]
            _cc = int(state.get("consecutive_correct") or 0)
            _ci = int(state.get("consecutive_incorrect") or 0)
            _prompt = (
                "学员刚完成一个技能点的全部固定题目（客观+简答）并宣告收尾。"
                "请结合学习表现给出 0-100 的主观掌握度评分（整数，只输出数字）。\n"
                f"技能点：{'、'.join(_titles) or '未知'}\n"
                f"教学状态：最近连续答对 {_cc} 题、连续答错 {_ci} 题。"
            )
            _resp = self._llm.chat(
                [{"role": "user", "content": _prompt}],
                system="你是导游资格证带教管家司南，负责对学员掌握情况给出主观评分。只输出 0-100 的整数，不要解释。",
                temperature=0.2,
                max_tokens=16,
            )
            import re as _re
            _mm = _re.search(r"\b(\d{1,3})\b", _resp.content or "")
            if _mm:
                ai_score = max(0, min(100, int(_mm.group(1))))
                for _kp in _kps:
                    try:
                        _ms.assess(self._current_user_id, _kp, "concierge", ai_score, "司南完成收尾时的主观评分")
                    except Exception:
                        pass
        except Exception:
            ai_score = None
        _mastery_state = None
        try:
            from brain_of_cloud.services.mastery import MasteryService
            _ms2 = MasteryService(self._plugin, self._store)
            if state.get("topic_ids"):
                _mastery_state = _ms2.skill_mastery(self._current_user_id, str(state["topic_ids"][0]))
        except Exception:
            _mastery_state = None
        return json.dumps(
            {
                "ok": True,
                "message": "已标记本技能点完成，系统会弹出完成去向卡（再学一个技能点 / 去5★沙盒 / 自由问答）。",
                "ai_score": ai_score,
                "mastery_state": _mastery_state,
                "teaching": self._teaching_public(state),
            },
            ensure_ascii=False,
        )


    def _recent_teaching_context(self, max_chars: int = 1600) -> str:
        """取本会话最近几条消息作为「刚才讲的内容」上下文（供简答出题智能体使用）。"""
        try:
            rows = self._store.get_session_messages(self._current_session_id)
        except Exception:
            return ""
        parts: list[str] = []
        total = 0
        for row in rows[-8:]:
            role = "学员" if row.get("role") == "user" else "司南"
            text = (row.get("content") or "").strip()
            if not text:
                continue
            piece = f"{role}：{text}"
            total += len(piece)
            if total > max_chars:
                piece = piece[: max(0, max_chars - (total - len(piece)))]
                parts.append(piece)
                break
            parts.append(piece)
        return "\n".join(parts)

    def _handle_submit_answer(self, question_id: str, answer: str, question_type: str | None = None) -> str:
        """判分：选择题走题库标准判分；简答题（question_type='essay'）走 AI 智能体 LLM 判分。"""
        if (question_type or "").strip().lower() == "essay":
            return self._handle_submit_essay(question_id, answer)
        try:
            result = self._training.submit(
                user_id=self._current_user_id,
                question_id=question_id,
                answer=answer,
            )
            mastery = self._training.get_mastery(self._current_user_id)
            adjustment = self._training.check_dynamic_thresholds(self._current_user_id)
        except KeyError as exc:
            return json.dumps({"error": f"未知题目: {exc}"}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"判分失败: {exc}"}, ensure_ascii=False)

        # ── 教学状态迁移：记录连续对错 → feedback；决策下一步动作 ──
        _pre = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
        _was_correct_before = question_id in set(_pre.get("quiz_correct") or [])
        state = self._teaching.record_answer(
            self._current_session_id, self._current_user_id,
            question_id, result.correct,
        )
        if result.correct:
            next_action = (
                "advance" if state["consecutive_correct"] >= 3 else "extend"
            )
        else:
            next_action = "reteach"
        angle = ""
        if not result.correct:
            try:
                angle = self._analyzer.reteach_angle(
                    self._current_user_id, question_id, answer, result
                )
            except Exception:
                angle = ""
        return json.dumps(
            {
                "correct": result.correct,
                "feedback": result.feedback,
                "score": result.score,
                "question_id": question_id,
                "misconception_tags": result.misconception_tags,
                "weak_point_titles": self._weak_point_titles(mastery.weak_points),
                "adjustment": adjustment,
                "reteach_hint": {
                    "need_reteach": not result.correct,
                    "angle": angle,
                    "next_action": next_action,
                    "misconception_tags": result.misconception_tags,
                },
                "repeat_correct": bool(result.correct and _was_correct_before),
                "teaching": self._teaching_public(state),
            },
            ensure_ascii=False,
        )

    def _handle_submit_essay(self, question_id: str, answer: str) -> str:
        """简答题判分：从教学状态取题目信息（rubric），调后台智能体 LLM 判分，落库 + 掌握度联动。"""
        state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
        last_quiz = state.get("last_quiz") or {}
        if not last_quiz or last_quiz.get("question_id") != question_id or last_quiz.get("type") != "essay":
            return json.dumps(
                {"error": "未找到对应的简答题（可能已换题），请重新出题"}, ensure_ascii=False
            )
        prompt = last_quiz.get("prompt", "")
        rubric = last_quiz.get("rubric", "")
        difficulty = last_quiz.get("difficulty") or state.get("depth") or "advanced"
        kp_id = last_quiz.get("knowledge_point_id") or (state.get("topic_ids") or [""])[0]

        def grader(p: str, r: str, a: str) -> tuple[bool, float, str]:
            return self._essay_agent.grade(p, r, a)

        try:
            result = self._training.submit_essay(
                user_id=self._current_user_id,
                question_id=question_id,
                knowledge_point_id=kp_id,
                difficulty=difficulty,
                prompt=prompt,
                rubric=rubric,
                answer=answer,
                grader=grader,
            )
            mastery = self._training.get_mastery(self._current_user_id)
            adjustment = self._training.check_dynamic_thresholds(self._current_user_id)
        except Exception as exc:
            return json.dumps({"error": f"简答题判分失败: {exc}"}, ensure_ascii=False)

        # ── 教学状态迁移：与选择题同构（连续对错 → feedback；决策下一步动作）──
        state = self._teaching.record_answer(
            self._current_session_id, self._current_user_id, question_id, result.correct,
        )
        if result.correct:
            next_action = "advance" if state["consecutive_correct"] >= 3 else "extend"
        else:
            next_action = "reteach"
        angle = ""
        if not result.correct:
            try:
                angle = self._analyzer.reteach_angle(
                    self._current_user_id, question_id, answer, result
                )
            except Exception:
                angle = ""
        return json.dumps(
            {
                "correct": result.correct,
                "feedback": result.feedback,
                "score": result.score,
                "question_id": question_id,
                "question_type": "essay",
                "misconception_tags": [],
                "weak_point_titles": self._weak_point_titles(mastery.weak_points),
                "adjustment": adjustment,
                "reteach_hint": {
                    "need_reteach": not result.correct,
                    "angle": angle,
                    "next_action": next_action,
                    "misconception_tags": [],
                },
                "teaching": self._teaching_public(state),
            },
            ensure_ascii=False,
        )

    def _handle_generate_report(self) -> str:
        user_id = self._current_user_id
        try:
            mastery = self._training.get_mastery(user_id)
            report = self._analyzer.run(user_id)
        except Exception:
            mastery = self._training.get_mastery(user_id)
            report = mastery
        weak_titles = self._weak_point_titles(mastery.weak_points)
        recommendation = getattr(report, "recommended_action", "") or ""
        report_text = (
            "## 学习进度报告\n\n"
            f"薄弱知识点：{'、'.join(weak_titles) if weak_titles else '暂无'}\n\n"
            f"下一步建议：{recommendation}\n\n"
            f"已学习技能点：{len(mastery.knowledge_point_scores)} / {self._total_skills()}"
        )
        asset = self._assets.create(
            user_id=user_id,
            session_id=self._current_session_id,
            title="学习进度报告",
            content=report_text,
            asset_type=AssetType.REPORT,
            source_tool="generate_report",
        )
        return json.dumps(
            {
                "scores": report.knowledge_point_scores,
                "weak_points": mastery.weak_points,
                "weak_point_titles": weak_titles,
                "recommendation": recommendation,
                "asset_id": asset.get("asset_id", ""),
                "title": asset.get("title", ""),
                "asset_type": asset.get("asset_type", "report"),
            },
            ensure_ascii=False,
        )

    def _handle_generate_plan(self) -> str:
        user_id = self._current_user_id
        profile = self._store.get_learner_profile(user_id)
        try:
            mastery = self._training.get_mastery(user_id)
        except Exception:
            mastery = None
        weak_points = list(mastery.weak_points) if mastery else []
        weak_titles = self._weak_point_titles(weak_points)
        mastered_count = len((mastery.knowledge_point_scores if mastery else {}))
        memories = self._memory.list_memories(user_id, limit=8)
        try:
            plan = self._planner.run(
                user_id=user_id,
                profile=profile,
                weak_points=weak_points,
                weak_point_titles=weak_titles,
                mastered_count=mastered_count,
                total_skills=self._total_skills(),
                recent_memories=memories,
            )
        except Exception as exc:
            return json.dumps({"error": f"计划生成失败: {exc}"}, ensure_ascii=False)
        asset = self._assets.create(
            user_id=user_id,
            session_id=self._current_session_id,
            title="个性化备考计划",
            content=plan,
            asset_type=AssetType.PLAN,
            source_tool="generate_plan",
        )
        return json.dumps(
            {
                "plan": plan,
                "asset_id": asset.get("asset_id", ""),
                "title": asset.get("title", ""),
                "asset_type": asset.get("asset_type", "plan"),
                "weak_point_titles": weak_titles,
            },
            ensure_ascii=False,
        )

    def _handle_update_profile(self, background: str) -> str:
        try:
            # 注入学情画像（先验问卷/结构化画像）与实测掌握度，供画像 Agent 校准等级与基线
            onboarding_ctx = None
            mastery_ctx = None
            uid = self._current_user_id
            try:
                onboarding_ctx = self._store.get_onboarding_profile(uid)
            except Exception:
                onboarding_ctx = None
            try:
                m = self._training.get_mastery(uid)
                mastery_ctx = {
                    "scores": dict(getattr(m, "knowledge_point_scores", {}) or {}),
                    "weak_points": list(getattr(m, "weak_points", []) or []),
                }
            except Exception:
                mastery_ctx = None
            profile = self._profile.generate_profile(
                uid, background,
                onboarding=onboarding_ctx,
                mastery=mastery_ctx,
            )
            self._store.save_learner_profile(profile)
            # 画像同时沉淀为长期记忆
            self._memory.add_memory(
                self._current_user_id, "background", f"背景：{background[:120]}",
                importance=0.7, source_session=self._current_session_id,
            )
            if profile.target_role:
                self._memory.add_memory(
                    self._current_user_id, "goal", f"目标：{profile.target_role}",
                    importance=0.9, source_session=self._current_session_id,
                )
            return json.dumps(
                {"level": profile.current_level, "style": profile.style_preferences},
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    # ================= 会话管理 =================

    def clear_session(self, session_id: str) -> None:
        with self._sessions_lock:
            self._sessions.pop(session_id, None)
        self._store.clear_session_messages(session_id)
        self._store.delete_teaching_state(session_id)
        self._store.delete_session_summary(session_id)

    # ================= 主入口 =================

    def handle_user_message(
        self,
        user_id: str,
        session_id: str,
        content: str,
        phase_cb: Callable[[str], None] | None = None,
        trace_cb: Callable[[dict], None] | None = None,
    ) -> OrchestratorResult:
        self._user_id_ctx.set(user_id)
        self._session_id_ctx.set(session_id)
        self._trace_cb_ctx.set(trace_cb)

        def _report(phase: str) -> None:
            if phase_cb is not None:
                try:
                    phase_cb(phase)
                except Exception:
                    pass

        _report("working")
        task = self._store.create_task(user_id=user_id, session_id=session_id, plugin_id=self._plugin.manifest["plugin_id"])
        # ── 多 Agent 实时轨迹：司南（管家）接收任务 ──
        self._emit_trace("concierge", "司南管家", "接收问题 · 规划分工", "working")
        input_message = self._store.create_message(
            task_id=task.task_id, from_agent=AgentId.CONCIERGE,
            content=content, visibility=Visibility.GROUP,
            mentions=[
                Mention(agent_id=AgentId.CONCIERGE, reason="user_message"),
            ],
        )

        # ── 加载或创建会话历史（加锁防止并发请求竞态）──
        with self._sessions_lock:
            if session_id not in self._sessions:
                history = self._store.get_session_messages(session_id)
                if history:
                    self._sessions[session_id] = [
                        {"role": "system", "content": self._concierge.config.system_prompt},
                        *history,
                    ]
                else:
                    self._sessions[session_id] = [
                        {"role": "system", "content": self._concierge.config.system_prompt},
                    ]

            # ── 注入每用户上下文（画像 + 记忆 + 薄弱点 + 教学状态），让管家个性化 ──
            user_context = self._build_user_context(user_id)
            base_system = self._sessions[session_id][0]

            # ── 上下文管理（T7）：长会话 → 早前对话摘要 + 保留窗口 ──
            raw_history = [
                m for m in self._sessions[session_id][1:]
                if m.get("role") != "system"
            ]
            managed_history = self._apply_context_management(session_id, user_id, raw_history)

            conversation = [
                base_system,
            ]
            if user_context:
                conversation.append({"role": "system", "content": user_context})
            # ── 先验画像模式（身份题未完成）：管家用 ask/submit_identity_* 在对话里推进 ──
            try:
                if not self._store.get_onboarding_profile(user_id):
                    _qa0 = self._store.get_onboarding_qa(user_id)
                    if int(_qa0.get("step") or 0) < len(_IDQ):
                        conversation.append({
                            "role": "system",
                            "content": (
                                "【先验画像模式】学员尚未完成先验学情画像的身份题。流程："
                                "① 调用 ask_identity_question 向学员出示当前题卡（前端会自动渲染卡片，不要复述选项原文）；"
                                "② 等学员作答后调用 submit_identity_answer 记录（answer=选项字母或原文），它会自动推进；"
                                "③ 未到第 6 题就继续调用 ask_identity_question 出下一题；"
                                "④ 第 6 题完成（返回 identity_done=true）后，向学员说明可以开始能力自评，"
                                "不要再使用知识教学/出题类工具。"
                            ),
                        })
            except Exception:
                pass
            conversation.extend(managed_history)
            conversation.append({"role": "user", "content": content})

        # ── 纠错中收到消息：给管家注入纠错上下文（作答必须 submit_answer；禁止换题/出新题）──
        try:
            _ts0 = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            if _ts0.get("reteach_question_id") and not _ts0.get("reteach_question"):
                # 快照丢失（异常/旧数据）→ 解除纠错态，避免无法出题
                self._teaching.finish_reteach(self._current_session_id, self._current_user_id)
            if _ts0.get("reteach_question_id"):
                _rq0 = _ts0.get("reteach_question") or {}
                _rt0 = f"（题干：{str(_rq0.get('prompt') or '')[:40]}…）" if _rq0.get("prompt") else ""
                conversation.append({
                    "role": "system",
                    "content": (
                        "【纠错进行中】学员正在重答刚才那道错题" + _rt0 + "（答题卡片已展示）。"
                        "若学员这条消息是在作答（如「我选 A/B/C/D」或「我的回答：…」），请立即调 submit_answer "
                        "判分（question_id=错题的 id，answer=对应字母/文字）；答错就输出降维解释并让学员在卡片重答，"
                        "答对就正常肯定并可在学员同意后进入下一题。在学员答对这道错题之前，"
                        "禁止调用 quiz_user / generate_essay_question，也不要自己复述题目或展示新题。"
                    ),
                })
        except Exception:
            pass

        tools_called: list[str] = []
        generated = ""
        review_verdict = ""
        hat_details: dict[AgentId, AgentResult] | None = None
        rounds = 0
        generation_count = 0
        material_nudges = 0  # 材料请求硬约束引导次数（防管家「话太多」不生成资产）
        revision_nudges = 0  # 审查未通过后的修订引导次数（防管家不修订直接交付）
        review_unresolved = False  # 最近一次审查未通过且尚未修订完成
        assets_created: list[dict[str, object]] = []
        reteach_text = ""  # 纠错讲解文本（答错后管家「讲解+再出题」同轮产出时留存）
        pending_reteach = False  # 判分答错 → 下一轮管家的讲解文本需要捕获
        submit_outcome: dict[str, object] | None = None  # 本轮 submit_answer 判分结果（程序化纠错闭环用）
        _turn_reteach_qid = ""  # 本轮答错的题（纠错闭环：同题卡片重问，直到答对才换下一题）
        reteach_nudges = 0  # 纠错闭环不合格被打回重做的次数（防止无限打回）
        _correct_answered_qid = ""  # 本轮答对的题（答对后同题卡片不再重现，防止重复/卡住）

        # ── 守门准备：学员本条是否在“答题卡片上作答”（若是，管家必须先调 submit_answer 判分）──
        _user_answering = False
        _answer_gate = 0
        try:
            _tsE = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            _lqE = _tsE.get("last_quiz") or {}
            if _lqE.get("question_id") and (_tsE.get("reteach_question_id") or _tsE.get("stage") == "practicing"):
                _user_answering = bool(re.match(r"^\s*我选\s*[A-Da-d]\s*$", content or "")) \
                    or (content or "").strip().startswith("我的回答：")
        except Exception:
            _user_answering = False


        try:
            max_iterations = 8  # safety limit
            time_budget_s = 240  # 单条消息总时间预算（秒）
            import time as _time
            _loop_t0 = _time.time()
            response: AgentResponse | None = None
            for _i in range(max_iterations):
                if _time.time() - _loop_t0 > time_budget_s:
                    print(f"[ORCH] time budget exceeded at iter={_i}", flush=True)
                    if response is not None and response.text:
                        break
                    response = AgentResponse(
                        text="处理耗时较长，已为你整理当前进展，如需更完整内容请告诉我具体方向。"
                    )
                    break
                conversation = self._sanitize_conversation(conversation)  # 防 400：保证 tool 消息紧跟 assistant(tool_calls)
                self._emit_trace("concierge", "旅鸢管家", "判断下一步分工", "working",
                                 step="planning", round=_i + 1, run_id=f"plan:{_i + 1}")
                response = self._concierge.think(conversation, self._tools.get_definitions())
                selected = []
                for raw in response.tool_calls or []:
                    if raw["name"] == "review_material":
                        ids = [a.value for a in self._HAT_TRACE] + ["blue_hat"]
                    else:
                        tm = self._TOOL_TRACE.get(raw["name"])
                        ids = [ALIASES.get(tm[0], tm[0])] if tm else []
                    for aid in ids:
                        if aid not in selected:
                            selected.append(aid)
                self._emit_trace("concierge", "旅鸢管家", "分工已确定", "done",
                                 step="dispatch", event="dispatch", round=_i + 1,
                                 agents=selected, tools=[t["name"] for t in response.tool_calls or []],
                                 run_id=f"plan:{_i + 1}",
                                 detail=f"本轮调度 {len(selected)} 个角色" if selected else "本轮由管家直接组织回复")
                _iter_tools = [t["name"] for t in (response.tool_calls or [])]
                print(
                    f"[ORCH] iter={_i} t={_time.time()-_loop_t0:.0f}s tools={_iter_tools} "
                    f"text={len(response.text or '')} review={review_verdict} gen={generation_count}",
                    flush=True,
                )
                # 纠错讲解文本捕获：答错后管家「讲解 + 再出题」同轮产出时，讲解文本会被
                # 后续工具轮吞掉（用户只看到新题）。此处留存，最终回复时合并给用户。
                if pending_reteach and response.text and response.tool_calls:
                    reteach_text = response.text
                    pending_reteach = False

                if response.tool_calls:
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": response.text or None,
                        "tool_calls": [
                            {
                                "id": tc_raw["id"],
                                "type": "function",
                                "function": {
                                    "name": tc_raw["name"],
                                    "arguments": json.dumps(tc_raw["arguments"], ensure_ascii=False),
                                },
                            }
                            for tc_raw in response.tool_calls
                        ],
                    }
                    if response.reasoning_content:
                        assistant_msg["reasoning_content"] = response.reasoning_content
                    conversation.append(assistant_msg)

                    for tc_raw in response.tool_calls:
                        tc = ToolCall(id=tc_raw["id"], name=tc_raw["name"], arguments=tc_raw["arguments"])
                        tools_called.append(tc.name)
                        # ── 多 Agent 实时轨迹：工具调用开始（对应 Agent 进入工作，附分工说明）──
                        _tr_meta = self._TOOL_TRACE.get(tc.name)
                        if _tr_meta:
                            self._emit_trace(_tr_meta[0], _tr_meta[1], _tr_meta[2], "working",
                                             detail=self._tool_work_note(tc), step="collaboration", run_id=tc.id)
                        # 群组空间审计：工具调用 → agent_run（差距项 T5）
                        run = self._agent_run_for_tool(task.task_id, input_message.message_id, tc.name)
                        # ── 纠错闭环锁：reteach 未解除前，禁止执行换题/出新题工具（工具层拦截，不插消息防400）──
                        _lock_tool = False
                        try:
                            _ts_x = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
                            if (tc.name in ("quiz_user", "generate_essay_question")) and _ts_x.get("reteach_question_id"):
                                _lock_tool = True
                        except Exception:
                            _lock_tool = False
                        if _lock_tool:
                            result = ToolResult(
                                id=tc.id, name=tc.name,
                                content=json.dumps({
                                    "error": "reteach_lock",
                                    "message": (
                                        "纠错闭环锁定中：学员还没答对刚才那道错题，不能换题/出新题。"
                                        "请只输出降维解释并让学员在下方卡片重答；答对后再继续。"
                                    ),
                                }, ensure_ascii=False),
                            )
                        else:
                            try:
                                result = self._tools.execute(tc)
                            except Exception as tool_exc:
                                result = ToolResult(
                                    id=tc.id, name=tc.name,
                                    content=json.dumps({"error": f"工具 {tc.name} 执行失败: {tool_exc}"}, ensure_ascii=False),
                                )
                        # ── 多 Agent 实时轨迹：工具调用结束（成功/失败）──
                        if _tr_meta:
                            _tr_fail = False
                            try:
                                _tr_parsed = json.loads(result.content)
                                _tr_fail = isinstance(_tr_parsed, dict) and bool(_tr_parsed.get("error"))
                            except Exception:
                                _tr_fail = False
                            self._emit_trace(
                                _tr_meta[0], _tr_meta[1], _tr_meta[2],
                                "failed" if _tr_fail else "done",
                                step="collaboration", run_id=tc.id,
                            )
                        if run is not None:
                            try:
                                self._store.complete_agent_run(run.run_id)
                            except KeyError:
                                pass
                            try:
                                self._store.append_message_mentions(
                                    input_message.message_id,
                                    [Mention(agent_id=run.agent_id, reason=f"tool:{tc.name}")],
                                )
                            except KeyError:
                                pass

                        # ── 消息交互日志（T15 / D-8）：每次智能体交互留痕，供偏好提取与审计 ──
                        try:
                            self._store.append_interaction_log(
                                user_id=user_id,
                                task_id=task.task_id,
                                message_id=input_message.message_id,
                                from_agent=self._TOOL_AGENT_MAP.get(tc.name, AgentId.CONCIERGE).value,
                                to_agents=[AgentId.CONCIERGE.value],
                                action=f"tool:{tc.name}",
                                content_summary=str(result.content)[:120],
                            )
                        except Exception:
                            pass

                        # ── 工具结果消息必须紧跟 assistant(tool_calls) 追加（OpenAI 严格约束：
                        # tool_calls 后只能跟对应 tool 消息，中间插入 system 会触发 400）──
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": self._tool_result_for_conversation(tc.name, result.content),
                        })

                        # ── 答题闭环（程序状态机）：捕获判分结果，后续统一由代码决策 ──
                        if tc.name == "submit_answer":
                            try:
                                submit_outcome = json.loads(result.content)
                            except Exception:
                                submit_outcome = None

                        if tc.name == "generate_material":
                            generation_count += 1
                            try:
                                generated = json.loads(result.content).get("content", "")
                            except Exception:
                                pass
                        if tc.name == "review_material":
                            _report("reviewing")
                            try:
                                rv = json.loads(result.content)
                                review_verdict = rv.get("verdict", "")
                                rounds += 1
                                review_unresolved = review_verdict == "needs_revision"
                            except Exception:
                                pass
                        if tc.name in ("generate_material", "generate_plan", "generate_report"):
                            try:
                                rv = json.loads(result.content)
                                aid = rv.get("asset_id", "")
                                if aid:
                                    assets_created.append(
                                        {
                                            "asset_id": aid,
                                            "title": rv.get("title", ""),
                                            "asset_type": rv.get("asset_type", "text"),
                                        }
                                    )
                            except Exception:
                                pass

                            # ── 帽子审查全覆盖（硬约束）：所有资产生成必须过六帽审查 ──
                            # 管家未自觉调 review_material 时，代码层自动触发；已审查过则跳过
                            if tc.name == "review_material":
                                pass  # 管家自己审查的路径（上面已处理）
                            else:
                                try:
                                    rv = json.loads(result.content)
                                    gen_content = (
                                        rv.get("content") or rv.get("plan") or ""
                                    )
                                    if not gen_content and rv.get("asset_id"):
                                        asset = self._store.get_asset(rv["asset_id"])
                                        gen_content = (asset or {}).get("content", "")
                                    if gen_content and "review_material" not in tools_called \
                                            and "review_material" not in _iter_tools:
                                        _report("reviewing")
                                        self._emit_trace("concierge", "旅鸢管家", "追加质量检查分工", "done",
                                                         step="dispatch", event="dispatch", source="policy", round=_i + 1,
                                                         agents=[aid.value for aid in self._HAT_TRACE] + ["blue_hat"],
                                                         tools=["review_material"], detail="资产生成后按质量检查规则追加六帽审查")
                                        review_result = self._handle_review_material(gen_content)
                                        rv2 = json.loads(review_result)
                                        review_verdict = rv2.get("verdict", "")
                                        rounds += 1
                                        review_unresolved = review_verdict == "needs_revision"
                                        # 审查意见全文注入（让管家知道改什么；必须用 system 角色，
                                        # tool 角色会因 tool_call_id 重复触发 OpenAI 400）
                                        conversation.append({
                                            "role": "system",
                                            "content": (
                                                "【六帽审查意见（针对你刚生成的内容）】\n"
                                                + review_result
                                            ),
                                        })
                                        conversation.append({
                                            "role": "system",
                                            "content": (
                                                f"系统提示：你刚生成的内容已自动完成六帽审查，"
                                                f"判定：{'合格' if review_verdict == 'passed' else '需修改'}。"
                                                + (
                                                    "无需再调 review_material，直接向学员交付"
                                                    if review_verdict == "passed"
                                                    else "请阅读上一条审查意见，立即调用 generate_material 修订（evidence 沿用刚才的证据）。"
                                                )
                                            ),
                                        })
                                except Exception:
                                    pass



                    # ── 答题纠错闭环：答错 → 降维解释 → 同一题答题卡片重问 → 直到答对；
                    # 答对解除纠错后节奏交还管家（可调 quiz_user 抽新题）。管家换题/出新题 → 打回重做。──
                    if submit_outcome is not None:
                        try:
                            _need = bool((submit_outcome.get("reteach_hint") or {}).get("need_reteach"))
                            _qid = str(submit_outcome.get("question_id") or "")
                            _ok = bool(submit_outcome.get("correct"))
                            if _need and _qid:
                                # ① 答错：进入纠错重问（记录同一题，直到答对它）
                                _turn_reteach_qid = _qid
                                try:
                                    _snap = self._reteach_question_snapshot(_qid)
                                except Exception:
                                    _snap = None
                                if _snap:
                                    self._teaching.begin_reteach(
                                        self._current_session_id, self._current_user_id, _snap
                                    )
                                pending_reteach = True
                                _angle = (submit_outcome.get("reteach_hint") or {}).get("angle") or ""
                                _mis = (submit_outcome.get("reteach_hint") or {}).get("misconception_tags") or []
                                _mis_txt = "、".join(str(x) for x in _mis) if _mis else "无"
                                conversation.append({
                                    "role": "system",
                                    "content": (
                                        "学员答错了这道题，现在进入纠错教学（降维解释）。你的职责只限两点："
                                        "① 用大白话讲清为什么错、正确思路与一句话记忆"
                                        "（错因标签：" + _mis_txt
                                        + (f"；可参考重讲切入点：{_angle}" if _angle else "")
                                        + "）；"
                                        "② 用 1 句自然的话让学员再试一次（如「别急，再看一遍这道题再选一次」）。"
                                        "这是硬性分工，你只负责解释与上下文衔接：题目和选项会由系统以答题卡片"
                                        "自动重新展示，你绝对不要在回复里重复题目原文或选项，绝对不能调用"
                                        "quiz_user / generate_essay_question 换题或再出题，也不要调用任何其他工具。"
                                        "解释完直接结束本轮回复。"
                                    ),
                                })
                            elif _ok:
                                _correct_answered_qid = _qid
                                print(f"[CTRL] submit correct qid={_qid} repeat={bool(submit_outcome.get('repeat_correct'))}", flush=True)
                                # ② 答对：解除纠错标记；若这是重问题的收口，或重复答对已掌握的题，
                                #    由程序直接抽下一题（前端卡片展示），管家只写衔接语。
                                try:
                                    _resolved = self._teaching.finish_reteach(
                                        self._current_session_id, self._current_user_id, _qid
                                    )
                                except Exception:
                                    _resolved = False
                                if _resolved:
                                    # 纠错收口：解除同题重问标记后，把节奏交还给管家（可调 quiz_user 抽新题巩固）
                                    conversation.append({
                                        "role": "system",
                                        "content": (
                                            "学员答对了刚才那道错题，纠错闭环完成，系统已解除同题重问状态。"
                                            "你现在可以按教学节奏继续：若想继续巩固，请调 quiz_user 抽一道全新题"
                                            "（题库会自动排除所有已出过的题，绝不会再出刚才那道）；"
                                            "也可以补一个延伸考点，或询问学员是否继续 / 换主题。"
                                            "不要停留或复述刚才那道题。"
                                        ),
                                    })
                                elif bool(submit_outcome.get("repeat_correct")):
                                    # 重复答对已掌握的题 → 编排器直接抽新题注入（防死循环，保持原有安全网）
                                    self._auto_next_quiz(conversation)
                                # ── 还差题库进阶简答（★5 固定题）→ 引导管家继续，不许提前“收工” ──
                                try:
                                    _tsC = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
                                    _tpcC = list(_tsC.get("topic_ids") or [])
                                    _doneC = self._training.correct_question_ids(self._current_user_id)
                                    _objC = self._training.topic_objective_pool(_tpcC)
                                    _objDone = bool(_objC) and all(q.question_id in _doneC for q in _objC)
                                    _essLeft = [
                                        q for q in self._training.topic_question_pool(_tpcC)
                                        if not q.options and q.question_id not in _doneC
                                    ]
                                    if _objDone and _essLeft:
                                        conversation.append({
                                            "role": "system",
                                            "content": (
                                                "该主题客观题已完成，题库里还有 " + str(len(_essLeft))
                                                + " 道进阶简答（难度5星）没做。若学员愿意，主动询问并调 "
                                                "generate_essay_question 出下一道简答；在全部完成前，不要宣布“全部完成/收工”。"
                                            ),
                                        })
                                except Exception:
                                    pass
                        except Exception:
                            pass


                    # ── 终止条件：审查通过 → 交付 ──
                    if review_verdict == "passed":
                        conversation.append({
                            "role": "system",
                            "content": "这份材料已通过质量审查。现在向学员交付：一句话说清生成了什么文件、已保存到学习中心，"
                                       "再把材料最核心的 2-3 点用大白话讲出来。不要调用任何工具，不要描述审查过程。"
                                       "**严禁在聊天里粘贴、复述或引用材料正文**——文件内容只保存在学习中心的资产里。",
                        })
                        response = self._deliver(conversation, generated, "材料已生成，保存在你的学习中心：\n\n")
                        break

                    # ── 终止条件：审查轮次超标 → 交付当前内容 ──
                    if rounds >= 2:
                        if review_unresolved:
                            conversation.append({
                                "role": "system",
                                "content": (
                                    "内容经多轮审查仍未通过。交付时请向学员如实说明："
                                    "材料已生成并保存，但其中部分内容经质量核查仍有疑问，"
                                    "建议重点核对后再使用（不要假装审查通过了）。"
                                ),
                            })
                        response = self._deliver(conversation, generated, "材料已生成，保存在你的学习中心：\n\n")
                        break

                    # ── 终止条件：生成次数超标 → 交付当前内容 ──
                    if generation_count >= 3:
                        if review_unresolved:
                            conversation.append({
                                "role": "system",
                                "content": (
                                    "内容经多轮审查仍未通过。交付时请向学员如实说明："
                                    "材料已生成并保存，但其中部分内容经质量核查仍有疑问，"
                                    "建议重点核对后再使用（不要假装审查通过了）。"
                                ),
                            })
                        response = self._deliver(conversation, generated, "材料已生成，保存在你的学习中心：\n\n")
                        break

                    # ── 审查需修改 → 追加修订指令（最多 max_review_rounds 轮）──
                    if review_verdict == "needs_revision" and rounds <= self._max_review_rounds:
                        conversation.append({
                            "role": "system",
                            "content": (
                                "刚才的质量审查认为材料还需要修改。请阅读上一条 review_material 的审查意见，"
                                "再次调用 generate_material 修订材料（在 request 中说明要修改的内容，"
                                "evidence 沿用刚才检索到的证据 JSON）。修订后再调用 review_material 复查。"
                            ),
                        })
                        review_verdict = ""
                        continue

                    continue

                if response.text:
                    # ── 硬约束：审查未通过但管家想直接交付 → 强制引导修订（防交付未审查内容）──
                    if review_unresolved and revision_nudges < 2:
                        revision_nudges += 1
                        conversation.append({
                            "role": "system",
                            "content": (
                                "你上一轮生成的内容六帽审查未通过（需修改），现在不能直接交付。"
                                "请阅读审查意见，立即再次调用 generate_material/generate_plan 修订内容"
                                "（在 request 中说明修改点，evidence 沿用证据），修订后会自动重新审查。"
                            ),
                        })
                        continue
                    # ── 硬约束：材料请求但管家只输出长文、未生成资产 → 强制引导调工具（防「话太多」）──
                    if (
                        self._is_material_request(content)
                        and not any(t in tools_called for t in ("generate_material", "generate_plan"))
                        and material_nudges < 2
                    ):
                        material_nudges += 1
                        conversation.append({
                            "role": "system",
                            "content": (
                                "学员要的是材料文件（讲义/笔记/总结/文档/指南），不是口头讲解。"
                                "请先调 search_knowledge 检索证据，再调 generate_material 生成材料资产"
                                "（request 写清需求，evidence 传检索结果 JSON），生成后调 review_material 审查；"
                                "聊天里只给简短交付语，正文放在材料文件里。"
                            ),
                        })
                        continue
                    # ── 纠错闭环守卫（打回去）：纠错中管家想直接结束 / 换题，但未给出实质降维解释 → 打回重做 ──
                    if _turn_reteach_qid and not reteach_text and reteach_nudges < 2:
                        _rt = (response.text or "")
                        _rt_violate = len(_rt.strip()) < 12 or any(
                            _k in _rt for _k in ("下一题", "换一道", "换一题", "再出一题", "出新题", "再来一道")
                        )
                        if _rt_violate:
                            reteach_nudges += 1
                            conversation.append({
                                "role": "system",
                                "content": (
                                    "你刚才的回复不符合纠错闭环要求（学员答错后必须先给降维解释，且不能自行换题/出下一题）。"
                                    "请重做：用大白话讲清为什么错、正确思路、一句话记忆，再自然地说一句让学员再试一次。"
                                    "题目会由系统以答题卡片自动重新显示，不要复述题目，也不要调用任何工具。"
                                ),
                            })
                            continue

                    # ── 管家调度守门（打回去）：学员已在答题卡片作答，但管家没调 submit_answer 就想结束 → 说明它忘了判分，打回重做 ──
                    if _user_answering and "submit_answer" not in tools_called and _answer_gate < 2:
                        _answer_gate += 1
                        conversation.append({
                            "role": "system",
                            "content": (
                                "你刚才忘了判分：学员在答题卡片上作答了（题目就是最近展示的那张卡），"
                                "你应该先调 submit_answer 判分（选择题传选项字母，简答题传文字），再根据判分结果继续。"
                                "不要只口头点评、不要跳过判分、不要自己复述题目或换题。请重做。"
                            ),
                        })
                        continue

                    break
                else:
                    conversation.append({"role": "system", "content": "请用中文回复用户。"})
                    continue

            else:
                # 迭代耗尽仍未得到最终文本 → 用简短交付兜底（不输出文件全文）
                if generated:
                    response = AgentResponse(text="材料已经生成好啦，完整内容保存在你的学习中心，可随时查看 / 导出。")
                else:
                    response = AgentResponse(text="抱歉，刚才有点卡住了。你再说一遍需求？")

        except Exception as loop_exc:
            import traceback
            traceback.print_exc()
            self._store.update_task_status(task.task_id, TaskStatus.FAILED)
            self._emit_trace("concierge", "司南管家", "处理失败 · 已回滚", "failed", detail=str(loop_exc)[:100])
            return OrchestratorResult(
                task=task,
                input_message=Message(
                    message_id=f"in_{task.task_id}", task_id=task.task_id,
                    from_agent=AgentId.CONCIERGE, content=content, lsn=1,
                ),
                response=f"抱歉，处理你的请求时遇到技术问题：{loop_exc}。请稍后重试。",
                tool_calls_made=tools_called,
                generated_content=generated,
                review_verdict=review_verdict,
                hat_details=hat_details,
                rounds_used=rounds,
                assets=assets_created,
            )

        # ── 最终响应组装：信任管家口语化交付；无交付语才兜底给材料全文 ──
        raw = self._clean_delivery_text(response.text) if response.text else ""
        if reteach_text and raw and reteach_text not in raw:
            raw = f"{reteach_text}\n\n{raw}"
        # ── 答题卡片去重：题干/选项只以答题卡片呈现，剥离管家误粘贴的题目回显 ──
        if raw:
            raw = self._dedupe_card_question(raw)
        # ── 兜底：答错但管家未给出有效降维解释 → 用题库解析自动生成，保证解释不缺失 ──
        if _turn_reteach_qid and raw:
            _trim = raw.strip()
            if len(_trim) < 10 or _trim == "别急，再试一次，在下方卡片重新作答。":
                _auto = self._auto_reteach_text(_turn_reteach_qid)
                if _auto:
                    raw = _auto
        # ── 沉淀降维解释到错题记录，重建「易错题·降维解释」资源（每道错题一张卡片）──
        if _turn_reteach_qid:
            self._persist_reteach_note(_turn_reteach_qid, raw)
        if raw:
            response = AgentResponse(text=raw)
        elif generated:
            response = AgentResponse(text="已为你生成材料文件并保存到学习中心，可随时查看 / 导出。")
        else:
            response = AgentResponse(text="抱歉，没能整理出结果。你再说一遍需求？")

        # ── 本次生成了文件资产 → 告知用户已保存到学习中心 ──
        if assets_created and response.text and "学习中心" not in response.text:
            note = f"\n\n📁 已保存 {len(assets_created)} 份文件到学习中心，可随时查看 / 导出。"
            response = AgentResponse(text=response.text + note)

        # ── 讲解/答疑自动存档：管家每次知识点讲解或答疑都生成文档留存（学习中心资产）──
        try:
            archived = self._archive_lecture_if_needed(
                user_id, session_id, content, response.text, tools_called, conversation,
            )
            if archived and response.text and "存档" not in response.text:
                response = AgentResponse(
                    text=response.text + "\n\n📄 本次讲解已为你存档到学习中心，可随时查看。"
                )
        except Exception:
            pass

        # ── 防泄漏兜底：任何残留的 tool XML 都不进入最终对话（宁可清空也不展示）──
        _fin_txt = response.text or ""
        if _fin_txt:
            _fin_clean = self._clean_delivery_text(_fin_txt)
            if _fin_clean:
                response = AgentResponse(text=_fin_clean)
            elif "<" in _fin_txt:
                response = AgentResponse(text="已完成处理，请查看上方结果。")

        # ── 持久化最终回复 + 提取长期记忆 ──
        final_msg: dict[str, Any] = {"role": "assistant", "content": response.text}
        if response.reasoning_content:
            final_msg["reasoning_content"] = response.reasoning_content
        conversation.append(final_msg)

        # 写入缓存（不含每轮注入的用户上下文块）
        with self._sessions_lock:
            self._sessions[session_id] = [base_system, *conversation[2:-1], final_msg]

        # ── 纠错闭环收口：本轮答错 → 强制前端展示同一题答题卡片（程序控制，非管家文本）──
        if _turn_reteach_qid:
            self._force_reteach_card(_turn_reteach_qid)
        # ── 答题卡片收口：本轮答对后，若 last_quiz 仍是刚答对的同一题（管家未抽新题），
        #    不再重现该题卡片（回到反馈/等待状态），避免「答对后卡片又出现一次」──
        if _correct_answered_qid:
            try:
                _st_c = self._teaching.get_or_create(session_id, user_id)
                _lq_c = _st_c.get("last_quiz") or {}
                if str(_lq_c.get("question_id") or "") == _correct_answered_qid \
                        and not _st_c.get("reteach_question_id"):
                    print(f"[CTRL] no-card: answered={_correct_answered_qid} last={_lq_c.get('question_id')} reteach={_st_c.get('reteach_question_id')} -> feedback", flush=True)
                    _st_c["stage"] = "feedback"
                    self._teaching.save(_st_c)
            except Exception:
                pass

        # 教学状态快照（前端渲染教学主题/阶段/最近一题）
        try:
            teaching_snapshot = self._teaching_public(
                self._teaching.get_or_create(session_id, user_id)
            )
        except Exception:
            teaching_snapshot = None

        # 持久化到 SQLite（用户 + 助手消息）
        self._store.save_session_message(session_id, user_id, "user", content)
        self._store.save_session_message(session_id, user_id, "assistant", response.text)

        # 规则提取学员长期记忆
        self._memory.extract_from_message(user_id, session_id, content)
        # ── 多 Agent 实时轨迹：司南汇总交付 ──
        self._emit_trace("concierge", "旅鸢管家", "汇总各 Agent 成果", "done", detail="组织最终回复交付给你", step="delivery")

        completed = self._store.update_task_status(task.task_id, TaskStatus.COMPLETED)
        return OrchestratorResult(
            task=completed,
            input_message=Message(
                message_id=f"in_{task.task_id}", task_id=task.task_id,
                from_agent=AgentId.CONCIERGE, content=content, lsn=1,
            ),
            response=response.text,
            tool_calls_made=tools_called,
            generated_content=generated,
            review_verdict=review_verdict,
            hat_details=hat_details,
            rounds_used=rounds,
            assets=assets_created,
            teaching=teaching_snapshot,
        )

    # ================= 辅助 =================

    _ARCHIVE_MIN_LEN = 40  # 讲解/答疑回复最短长度（排除纯工具交付语/短回应）

    def _archive_lecture_if_needed(
        self,
        user_id: str,
        session_id: str,
        user_content: str,
        response_text: str,
        tools_called: list[str],
        conversation: list[dict[str, Any]],
    ) -> bool:
        """管家讲解/答疑后自动生成文档留存（学习中心资产）。

        触发条件（全部满足才存档）：
        - 回复是实质讲解内容（≥40 字）；
        - 本轮调用了 search_knowledge（知识点讲解/答疑的标志）；
        - 未走材料/计划/报告生成路径（那些路径已有自己的资产，避免重复）；
        - 用户消息不是材料生产请求（与管家判别一致）。
        存档内容：问题 + 讲解全文 + 知识来源（不暴露给对话，后台留存）。
        """
        if not response_text or len(response_text) < self._ARCHIVE_MIN_LEN:
            return False
        if "search_knowledge" not in tools_called:
            return False
        if any(t in tools_called for t in ("generate_material", "generate_plan", "generate_report")):
            return False
        if self._is_material_request(user_content):
            return False
        try:
            topic_title = self._lecture_topic_title()
            sources = self._lecture_sources_from(conversation)
            from datetime import datetime, timezone

            lines = [
                f"# 讲解笔记 · {topic_title}",
                "",
                f"> 司南对话讲解/答疑留存 · {datetime.now(timezone.utc).isoformat(timespec='minutes')}",
                "",
                "## 你的问题",
                user_content,
                "",
                "## 司南的讲解",
                response_text,
            ]
            if sources:
                lines += ["", "## 知识来源"] + [f"- {s}" for s in sources]
            asset = self._assets.create(
                user_id=user_id,
                title=f"讲解笔记 · {topic_title}",
                content="\n".join(lines),
                asset_type=AssetType.LECTURE,
                session_id=session_id,
                source_tool="lecture_archive",
            )
            return bool(asset)
        except Exception:
            return False

    def _lecture_topic_title(self) -> str:
        """讲解笔记标题主题：当前教学主题技能点标题；无则用会话名。"""
        try:
            state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            topic_ids = list(state.get("topic_ids") or [])
            if topic_ids:
                return self._skill_title(topic_ids[0])
        except Exception:
            pass
        return "答疑记录"

    def _lecture_sources_from(self, conversation: list[dict[str, Any]]) -> list[str]:
        """从本轮工具结果中提取 search_knowledge 的知识来源（出处，≤4 条）。"""
        out: list[str] = []
        for m in conversation:
            if m.get("role") != "tool":
                continue
            try:
                obj = json.loads(m.get("content") or "")
                if not isinstance(obj, dict) or "results" not in obj:
                    continue
                for r in (obj.get("results") or [])[:4]:
                    src = str(r.get("source") or "").strip()
                    if src and src not in out:
                        out.append(src)
            except Exception:
                continue
        return out[:4]

    _TOOL_XML_RE = re.compile(
        r"\\?<\s*tool_calls\b[^>]*>.*?\\?<\s*/\s*tool_calls\s*>"
        r"|\\?<\s*invoke\b[^>]*>.*?\\?<\s*/\s*invoke\s*>"
        r"|\\?<\s*parameter\b[^>]*>.*?\\?<\s*/\s*parameter\s*>",
        re.S | re.I,
    )
    _TOOL_LEAK_TAG_RE = re.compile(
        r"\\?<\s*/?\s*(?:tool_calls|invoke|parameter|arguments|function)\b[^>]*>",
        re.I,
    )

    def _strip_tool_markup(self, text: str) -> str:
        """剥离文本中泄漏的 XML 工具调用标记（含转义反斜杠/属性/嵌套等变体）。"""
        t = self._TOOL_XML_RE.sub("", text or "")
        # 去掉成对之外的残缺/散落标签
        t = self._TOOL_LEAK_TAG_RE.sub("", t)
        t = re.sub(r"[ \t]*\n{3,}", "\n\n", t)
        return t.strip()

    def _clean_delivery_text(self, text: str) -> str:
        """清理交付文本（防泄漏工具 XML）。"""
        return self._strip_tool_markup(text)

    def _tool_result_for_conversation(self, tool_name: str, raw: str) -> str:
        """工具结果注入对话前的裁剪。

        生成类工具（generate_material/plan/report）的结果含材料全文——
        原样注入会让管家在下一轮直接把文件内容复述成回复（材料正文只应
        存在于学习中心的资产文件里）。这里只保留元信息 + 交付纪律提示。
        """
        if tool_name not in ("generate_material", "generate_plan", "generate_report"):
            return raw
        try:
            rv = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
        return json.dumps(
            {
                "asset_id": rv.get("asset_id", ""),
                "title": rv.get("title", ""),
                "asset_type": rv.get("asset_type", "text"),
                "note": (
                    "材料全文已保存为学习中心文件资产，你不需要、也不允许复述它。"
                    "交付时只给一两句简短说明（生成了什么文件、存在哪、核心 2-3 点），"
                    "严禁把材料正文粘贴进聊天回复。"
                ),
            },
            ensure_ascii=False,
        )

    def _deliver(self, conversation: list[dict[str, Any]], generated: str, note: str) -> AgentResponse:
        """交付已生成材料。优先让管家写交付语；失败则直接给材料。"""
        try:
            conversation = self._sanitize_conversation(conversation)
            final = self._concierge.think(conversation, [])
            if final and final.text:
                cleaned = self._clean_delivery_text(final.text)
                if cleaned:
                    return AgentResponse(text=cleaned)
        except Exception:
            pass
        if generated:
            return AgentResponse(text="材料已生成，保存在你的学习中心，可随时查看 / 导出。")
        return AgentResponse(text="材料已生成，保存在你的学习中心，可随时查看 / 导出。")

    def _apply_context_management(
        self,
        session_id: str,
        user_id: str,
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """长会话上下文裁剪（T7）：超阈值 → 生成/复用「早前对话摘要」+ 保留窗口。

        - 未超阈值：原样返回
        - 已超阈值且有摘要：摘要 + 最近 MAX_KEEP 条
        - 已超阈值且距上次摘要新增 ≥REFRESH_STEP 条：增量重摘要并持久化
        """
        if self._context_mgr.overflow_count(history) <= 0:
            return history
        row = self._store.get_session_summary(session_id)
        existing = row["summary"] if row else None
        last_count = int(row["message_count"]) if row else 0
        if not self._context_mgr.should_summarize(history, existing, last_count):
            if existing:
                return self._context_mgr.apply(history, existing)
            return history
        new_summary = self._context_mgr.summarize(history, existing_summary=existing)
        if not new_summary:
            # 摘要失败（LLM 不可用等）：宁可保留全量，不可丢上下文
            return history
        self._store.save_session_summary(session_id, user_id, new_summary, len(history))
        return self._context_mgr.apply(history, new_summary)

    def _build_user_context(self, user_id: str) -> str:
        profile = self._store.get_learner_profile(user_id)
        try:
            mastery = self._training.get_mastery(user_id)
        except Exception:
            mastery = None
        weak_titles = self._weak_point_titles(list(mastery.weak_points)) if mastery else []
        ctx = self._memory.build_user_context(
            user_id,
            profile=profile,
            weak_point_titles=weak_titles,
            memory_limit=8,
        )
        # ── 结构化先验画像（onboarding）合并进管家上下文，让旧链路也能“看见”新画像 ──
        try:
            op = self._store.get_onboarding_profile(user_id)
            if op and op.get("persona"):
                pp = op["persona"]
                ctx += (
                    f"\n\n【学情画像（先验·结构化）】\n"
                    f"- 画像类型：{pp.get('label') or ''}\n"
                    f"- 画像摘要：{pp.get('summary') or ''}\n"
                    f"- 详细描述：{pp.get('description') or ''}"
                )
        except Exception:
            pass
        # ── 教学上下文注入（T6 persona：让管家清楚当前教什么，像老师一样自然衔接）──
        try:
            teaching = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            topic_ids = list(teaching.get("topic_ids") or [])
            if topic_ids:
                titles = [self._skill_title(kp) for kp in topic_ids]
                stage = teaching.get("stage") or "goal_setting"
                depth = teaching.get("depth") or "intro"
                cc = int(teaching.get("consecutive_correct") or 0)
                ci = int(teaching.get("consecutive_incorrect") or 0)
                stage_note = {
                    "goal_setting": "还在确定学习目标",
                    "teaching": "正在讲解中",
                    "checking": "正在确认理解",
                    "practicing": "正在练习",
                    "feedback": "正在讲评纠错",
                    "closing": "正在小结",
                    "idle": "空闲",
                }.get(stage, stage)
                ctx += (
                    f"\n\n【当前教学上下文】（这是你正在教的课，自然地衔接，不要装作不知道）\n"
                    f"- 这堂课的主题：{'、'.join(titles)}\n"
                    f"- 当前阶段：{stage_note}；当前难度档位：{depth}（intro=入门/basic=基础/"
                    f"advanced=进阶/comprehensive=综合）\n"
                    f"- 最近答题：连续答对 {cc} 题、连续答错 {ci} 题\n"
                    f"- 学员回到对话时，像一位老师接着上节课往下讲（例如「我们接着讲{ titles[0] }」），"
                    f"先回顾一句上节课讲到哪，再继续；不要从头重讲，也不要装作第一次认识这个主题。"
                )
        except Exception:
            pass
        # ── 错题本注入：反馈/复盘时让管家能引用具体错题 ──
        try:
            wa = self._training.wrong_answers(user_id, limit=5)
            if wa:
                wa_lines = [
                    f"- {w.get('skill_title') or '（未标注技能点）'}：{w.get('prompt')[:36]}…"
                    f"（你选了「{w.get('user_answer')}」，正确答案「{w.get('correct_answer')}」，错 {w.get('wrong_count')} 次）"
                    for w in wa
                ]
                ctx += (
                    "\n\n【易错题·降维解释（最近做错）】\n" + "\n".join(wa_lines)
                    + "\n（反馈时优先围绕这些错题纠错，帮学员搞清楚错在哪，而不是泛泛而谈）"
                )
        except Exception:
            pass
        return ctx

    # ================= 答题纠错闭环（程序状态机，不依赖管家自觉） =================

    def _reteach_question_snapshot(self, question_id: str) -> dict[str, object] | None:
        """取当前要重问的题（含题目/选项/难度/知识点标题），用于同题答题卡片重问。"""
        try:
            state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            lq = state.get("last_quiz") or {}
            if lq.get("question_id") == question_id and (lq.get("prompt") or lq.get("rubric")):
                return dict(lq)
        except Exception:
            pass
        q = None
        try:
            q = self._training.get_question(question_id)
        except Exception:
            q = None
        if q is None:
            return None
        return {
            "question_id": q.question_id,
            "type": "choice",
            "prompt": q.prompt,
            "options": list(q.options or []),
            "difficulty": q.difficulty,
            "difficulty_level": getattr(q, "difficulty_level", None),
            "knowledge_point_title": self._skill_title(q.knowledge_point_id),
        }

    def _auto_next_quiz(self, conversation: list[dict[str, Any]]) -> None:
        """答对收口（纠错解除 / 重复答对）后，由程序直接抽下一道新题（前端卡片展示）。
        管家只写 1-2 句衔接语，不展示题目、不再出题。"""
        try:
            self._emit_trace("concierge", "旅鸢管家", "答题闭环追加分工", "done", step="dispatch", event="dispatch",
                             source="policy", agents=["training_analyzer"], tools=["quiz_user"], detail="答对后按教学规则抽取下一道新题")
            self._emit_trace("training_analyzer", "测评分析师", "抽取下一道新题", "working", step="collaboration")
            nq = json.loads(self._handle_quiz_user())
            self._emit_trace("training_analyzer", "测评分析师", "题库抽题完成", "done", step="collaboration")
        except Exception:
            nq = {}
            self._emit_trace("training_analyzer", "测评分析师", "自动抽题失败", "failed", step="collaboration")
        if nq.get("question_id"):
            conversation.append({
                "role": "system",
                "content": (
                    "学员已经答对上一题。系统已自动从题库抽取下一道新题（已排除所有出过的题），"
                    "将直接以答题卡片展示。请你只回复 1-2 句简短衔接语（肯定学员 + 引导看下一题），"
                    "不要调 quiz_user / generate_essay_question，不要重复或转述上一题，"
                    "也不要把新题内容或选项写进回复。"
                ),
            })
            return
        if nq.get("type") == "essay_ready":
            conversation.append({
                "role": "system",
                "content": (
                    "学员已答对上一题，但当前教学主题的选择题已全部做完，没有更多选择题可抽。"
                    "请如实告诉学员，并按其意愿推荐进阶简答题（学员同意后再调 generate_essay_question）。"
                ),
            })
            return
        conversation.append({
            "role": "system",
            "content": (
                "学员已答对上一题，但题库暂时没有更多新题可出。请如实告诉学员，"
                "询问是换一个知识点继续学，还是把当前知识点再讲深一点；不要重复已做过的题。"
            ),
        })

    def _force_reteach_card(self, question_id: str) -> None:
        """纠错闭环收口：确保本轮答错后，前端教学快照回到「同一题答题卡片」重问。"""
        if not question_id:
            return
        try:
            state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            if str(state.get("reteach_question_id") or "") == question_id and state.get("reteach_question"):
                state["last_quiz"] = state["reteach_question"]
                state["stage"] = "practicing"
                self._teaching.save(state)
        except Exception:
            pass

    def _sanitize_conversation(self, conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """修复对话消息顺序，避免 OpenAI/DeepSeek 400。

        - role=tool 必须紧跟带 tool_calls 的 assistant 消息；
        - 工具结果之间被 system/user 打断 → 暂存到工具结果之后；
        - 找不到对应 assistant(tool_calls) 的孤立 tool 消息 → 丢弃（上下文裁剪可能切断配对）；
        - 结尾仍未收齐工具结果的 assistant(tool_calls) → 连同缺失结果一起移除，防止缺结果报错。
        """
        if not conversation:
            return conversation
        out: list[dict[str, Any]] = []
        pending: set[str] = set()
        stash: list[dict[str, Any]] = []

        def _flush() -> None:
            if stash:
                out.extend(stash)
                stash.clear()

        for m in conversation:
            role = m.get("role")
            if pending:
                if role == "tool" and m.get("tool_call_id") in pending:
                    out.append(m)
                    pending.discard(m.get("tool_call_id") or "")
                    if not pending:
                        _flush()
                    continue
                # 工具结果未收齐时混入其它角色 → 先暂存，等工具结果收齐再放回
                stash.append(m)
                continue
            if role == "assistant" and m.get("tool_calls"):
                out.append(m)
                pending = {str(tc.get("id") or "") for tc in m["tool_calls"]}
                continue
            if role == "tool":
                # 孤立 tool（前面没有 assistant(tool_calls)）→ 直接丢弃，防 400
                continue
            out.append(m)
        _flush()
        if pending:
            # 仍有未收齐的工具结果：把发起这些调用的 assistant(tool_calls) 与残留 tool 一并移除
            out = [
                m for m in out
                if not (
                    (m.get("role") == "tool" and (m.get("tool_call_id") or "") in pending)
                    or (
                        m.get("role") == "assistant"
                        and m.get("tool_calls")
                        and any(str(tc.get("id") or "") in pending for tc in m["tool_calls"])
                    )
                )
            ]
        return out

    def _auto_reteach_text(self, question_id: str) -> str:
        """答错兜底降维解释：管家没给出有效解释时，用题库解析自动生成一句大白话。"""
        try:
            q = self._training.get_question(question_id)
        except Exception:
            q = None
        if q is None:
            return ""
        ans = (q.answer or q.answer_key or "").strip()
        expl = (q.explanation or "").strip()
        if not ans and not expl:
            return ""
        _parts = []
        if ans:
            _parts.append(f"正确答案：{ans}")
        if expl:
            _parts.append(expl)
        return "这道题先记结论：" + "；".join(_parts) + "。记住后再在下方卡片重选一次。"


    def _dedupe_card_question(self, text: str) -> str:
        """答题卡片去重：题干与选项只由答题卡片展示，剥离管家误粘贴的题目回显。

        只做「安全截断」，绝不动降维解释正文：
        - 纠错重问：仅当解释末尾出现明确的「原题再给你一次/重新选」重问段，或题干+≥2 个选项
          出现在文本靠后位置（明显是在复述题目）才截断；解释里顺带引用题干/选项绝不删；
        - 普通出题：题干后紧跟选项的整段回显（与卡片重复）→ 只保留题干之前的引导语。
        """
        if not text:
            return text
        reteach = False
        lq: dict[str, object] = {}
        try:
            state = self._teaching.get_or_create(self._current_session_id, self._current_user_id)
            lq = state.get("last_quiz") or {}
            reteach = bool(state.get("reteach_question_id"))
        except Exception:
            pass
        prompt = (lq.get("prompt") or "").strip()
        if not prompt or prompt not in text:
            return text

        def _cut_at(idx: int) -> str:
            kept = text[:idx].strip(" \n-—：:，。*#")
            if not kept:
                return "别急，再试一次，在下方卡片重新作答。" if reteach else "来做一道题检验一下吧，直接在下方卡片作答。"
            return kept

        # ① 明确的重问段（管家在解释后附加「把题目原样再给你」等）→ 从该句起截断
        if reteach:
            for _m in ("我把刚才这道题", "原样再给你", "原题再给你", "再给你一次", "重新选一下", "请重新作答", "再看一遍这道题", "你重新选一次"):
                _i = text.find(_m)
                if _i != -1:
                    return _cut_at(_i)

        # ② 题干后紧跟选项的整段回显（普通出题必然要去重）
        _idx = text.find(prompt)
        _tail = text[_idx + len(prompt):]
        _opts = [str(o).strip() for o in (lq.get("options") or []) if str(o).strip()]
        _echo = any(o in _tail for o in _opts)
        _echo = _echo or bool(re.search(r"(?m)^\s*[A-D]\s*[.、．]", _tail))
        if _echo:
            if not reteach:
                # 普通出题：管家念了一遍题干+选项 → 只保留引导语
                return _cut_at(_idx)
            # 纠错重问：只有当题目回显出现在整段文本靠后位置（说明解释已说完、后面是复述）才截
            if _idx >= len(text) * 0.55 and len(_tail) >= 8:
                return _cut_at(_idx)
        return text

    def _persist_reteach_note(self, question_id: str, text: str) -> None:
        """把本轮降维解释沉淀到错题记录，并重建「易错题·降维解释」资源（每道错题一张卡片）。
        即使解释为空也会重建，保证答错后立即生成卡片。"""
        if not question_id:
            return
        try:
            note = (text or "").strip()
            if note:
                self._training.record_wrong_note(self._current_user_id, question_id, note)
            self._assets.sync_wrong_book(
                self._current_user_id,
                self._training.wrong_answers(self._current_user_id),
            )
        except Exception:
            pass


    def difficulty_curve(self, user_id: str, session_id: str) -> dict[str, object]:
        """动态难度曲线数据：按作答顺序给出每个难度点（含对错），并给出当前状态文案。

        - points 只含「已作答」的题（当前未作答的新题单独用 current 高亮，不误标红/绿）；
        - status：all_done / up(刚升星，已动态调整难度) / good / weak(降维解释中) / idle。
        """
        state = self._teaching.get_or_create(session_id, user_id)
        topic_ids = list(state.get("topic_ids") or [])
        q_history = list(state.get("quiz_history") or [])
        quiz_correct = set(state.get("quiz_correct") or [])
        correct_ids = set()
        try:
            correct_ids = self._training.correct_question_ids(user_id)
        except Exception:
            pass
        correct_ids |= quiz_correct

        last_quiz = state.get("last_quiz") or {}
        last_qid = str(last_quiz.get("question_id") or "")

        def _level_of(qid: str) -> int | None:
            try:
                q = self._training.get_question(qid)
            except Exception:
                q = None
            if q is None:
                return None
            if q.difficulty_level is not None:
                return int(q.difficulty_level)
            return {"intro": 1, "basic": 2, "advanced": 3, "comprehensive": 4}.get(q.difficulty or "", None)

        current_level = _level_of(last_qid) if last_qid else None
        points: list[dict[str, object]] = []
        prev_level: int | None = None
        for seq, qid in enumerate(q_history, 1):
            lv = _level_of(qid)
            if lv is None:
                continue
            answered = qid in correct_ids
            if qid == last_qid and not answered:
                # 当前题刚出还没作答：不算作已答点（避免误标红/绿）
                continue
            points.append({"seq": len(points) + 1, "difficulty_level": lv, "correct": answered})
            prev_level = lv

        # 上一轮真实作答结果：新题未作答时保持上一轮，避免误报“掌握不足”
        _outcome = state.get("last_outcome")
        reteaching = bool(state.get("reteach_question_id"))
        last_correct: bool | None = None
        if _outcome == "correct":
            last_correct = True
        elif _outcome == "wrong":
            last_correct = False

        # 主题客观题全答对？（固定题已做完）
        all_done = False
        pool: list = []
        if topic_ids:
            try:
                pool = self._training.topic_question_pool(topic_ids)
            except Exception:
                pool = []
            if pool:
                all_done = all(q.question_id in correct_ids for q in pool)

        next_level: int | None = None
        if not all_done and topic_ids:
            try:
                nq = self._training.next_progression_question(
                    topic_ids,
                    exclude_answered=set(q_history),
                    exclude_mastered=correct_ids,
                )
            except Exception:
                nq = None
            if nq is not None:
                next_level = _level_of(nq.question_id)

        status: dict[str, object] = {"code": "idle", "text": "", "can_sandbox": False}
        if all_done and last_correct is not False:
            status = {
                "code": "all_done",
                "text": "本主题固定题目已全部答完，是否挑战 5★ 难度沙盒挑战？",
                "can_sandbox": True,
            }
        elif reteaching or last_correct is False:
            status = {
                "code": "weak",
                "text": "当前掌握不足，已生成降维解释，请先在下方卡片重新作答。",
                "can_sandbox": False,
            }
        elif last_correct is True:
            if current_level is not None and prev_level is not None and current_level > prev_level:
                status = {
                    "code": "up",
                    "text": f"已根据掌握情况动态调整难度：当前 ★{current_level}，继续保持！",
                    "can_sandbox": False,
                }
            elif next_level is not None and current_level is not None and next_level > current_level:
                status = {"code": "up", "text": "当前掌握度良好，即将提升难度。", "can_sandbox": False}
            else:
                status = {"code": "good", "text": "当前掌握度良好，继续保持。", "can_sandbox": False}

        return {
            "points": points,
            "current": {
                "question_id": last_qid,
                "difficulty_level": current_level,
                "knowledge_point_title": (last_quiz.get("knowledge_point_title") or ""),
                "stage": state.get("stage") or "goal_setting",
            },
            "last_answer_correct": last_correct,
            "next_difficulty_level": next_level,
            "all_done": all_done,
            "stars_max": 5,
            "status": status,
        }

    def _teaching_public(self, state: dict[str, object]) -> dict[str, object]:
        """教学状态 → 对外快照（前端渲染用，不暴露内部字段）。"""
        topic_ids = list(state.get("topic_ids") or [])
        last_quiz = state.get("last_quiz") or None
        # 纠错重问进行中：无论持久化的阶段如何，都把重问题卡恢复出来（防止重进历史后卡消失）
        if state.get("reteach_question_id"):
            _rq = state.get("reteach_question")
            if _rq:
                last_quiz = _rq
        topic_done = False
        if topic_ids:
            try:
                _pool = self._training.topic_question_pool(topic_ids)
                if _pool:
                    _cids = self._training.correct_question_ids(str(state.get("user_id") or ""))
                    topic_done = all(q.question_id in _cids for q in _pool)
            except Exception:
                topic_done = False
        return {
            "session_id": state["session_id"],
            "stage": "practicing" if (state.get("reteach_question_id") and state.get("reteach_question")) else (state.get("stage") or "goal_setting"),
            "depth": state.get("depth") or "intro",
            "topics": [
                {"id": kp_id, "title": self._skill_title(kp_id)}
                for kp_id in topic_ids
            ],
            "consecutive_correct": int(state.get("consecutive_correct") or 0),
            "consecutive_incorrect": int(state.get("consecutive_incorrect") or 0),
            "last_quiz": last_quiz,
            "topic_done": topic_done,
            "topic_finished": bool(state.get("topic_finished")),
        }

    def _topic_mastery(self, user_id: str, kp_ids: list[str]) -> float | None:
        """当前教学主题的平均掌握度；从未练过返回 None（按新手处理）。"""
        try:
            mastery = self._training.get_mastery(user_id)
        except Exception:
            return None
        scores = mastery.knowledge_point_scores
        vals = [scores[kp] for kp in kp_ids if kp in scores]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def _skill_title(self, kp_id: str) -> str:
        """解析技能点 ID → 中文标题（兼容新旧插件）。"""
        getter = getattr(self._plugin, "get_skill", None)
        if getter is not None:
            skill = getter(kp_id)
            if skill is not None:
                return getattr(skill, "title", str(kp_id))
        for kp in self._plugin.list_knowledge_points():
            if kp.id == kp_id:
                return kp.name
        return kp_id

    _LECTURE_KW = ("讲义", "总结", "考点", "笔记", "材料", "知识点")
    _GUIDE_KW = ("实操", "指南", "步骤", "演练", "剧本", "话术", "模板")

    _MATERIAL_REQUEST_KW = (
        "讲义", "笔记", "总结", "文档", "材料", "指南", "模板", "考点", "整理",
        "生成一份", "做成", "复习资料", "要点梳理", "归纳", "汇成", "文件",
    )

    def _is_material_request(self, text: str) -> bool:
        """用户消息是否为「材料生产」请求（讲义/笔记/总结/文档…），区别于知识点提问。"""
        return any(k in text for k in self._MATERIAL_REQUEST_KW)

    def _infer_asset_type(self, request: str) -> AssetType:
        """根据需求描述推断生成物的资产类型（讲义类优先）。"""
        if any(k in request for k in self._LECTURE_KW):
            return AssetType.LECTURE
        if any(k in request for k in self._GUIDE_KW):
            return AssetType.PRACTICE_GUIDE
        return AssetType.TEXT

    def _asset_title(self, request: str) -> str:
        """从需求描述提炼资产标题（取首句，去引号）。"""
        title = request.strip().strip("“”\"'")
        for sep in ("。", "！", "？", "；", "，", " "):
            idx = title.find(sep)
            if 0 < idx < 24:
                title = title[:idx]
                break
        return title[:60]

    def _weak_point_titles(self, weak_points: list[str]) -> list[str]:
        return [self._skill_title(kp) for kp in weak_points]

    def _total_skills(self) -> int:
        stats = getattr(self._plugin, "stats", None)
        if callable(stats):
            return stats().get("skills", 3796)
        return len(self._plugin.list_knowledge_points())


































