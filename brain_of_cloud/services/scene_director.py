"""场景导演智能体 — 判定沙盒模拟场景的剧情走向与结束方式。

替代「固定对话轮次」限制：不再按轮次强制推进，由 LLM 依据剧情实质判定
continue / advance / complete / fail；代码仅在 LLM 输出解析失败时兜底
（信任崩塌 → fail；阶段轮数超防呆上限 → advance；否则 continue），永远不抛异常。

本模块顶层不运行时导入 sandbox.py（仅 TYPE_CHECKING），避免 t5 集成后
sandbox ↔ scene_director 循环导入；类型注解依赖 ``from __future__ import annotations``。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from brain_of_cloud.domain.models import AgentConfig, AgentId
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import BaseAgent

if TYPE_CHECKING:
    from brain_of_cloud.services.sandbox import CustomerProfile, SandboxTemplate


SCENE_DIRECTOR_SYSTEM_PROMPT = """\
你是导游资格证培训系统的「场景导演」，负责判定沙盒模拟场景当前的剧情走向：
对话是否结束、如何结束，或是否推进到下一阶段。你只依据剧情实质判定，不按固定对话轮次强推。

【判定规则（按优先级从高到低）】
1. 场景失败（action=fail，outcome=failed）：满足以下任一条件即判失败——
   a. 游客信任崩塌：游客信任度 < 20，且游客已明确表达「离团、投诉、不再信任导游」等意愿；
   b. 学员严重失误：导游出现辱骂游客、拒绝提供服务、严重违反法律法规等行为。
   reason 用中文说明搞砸的具体表现（20-60 字）。
2. 场景成功（action=complete，outcome=success）：仅当当前阶段是最后阶段，
   且本阶段关键目标已达成（游客对导游的服务实质满意，或对话已实质完成本阶段 objective，
   或游客给出 advanced 信号）。reason 用中文说明成功依据（20-60 字）。
3. 阶段推进（action=advance，outcome=null）：当前阶段关键目标已达成（判断标准同上），
   但场景还有后续阶段。reason 用中文说明推进依据（20-60 字）。
4. 继续对话（action=continue，outcome=null）：本阶段关键目标尚未达成，对话应继续展开。
   reason 用中文说明还差什么（20-60 字）。

【判断依据】
- 当前阶段标题与 objective、是否为最后阶段；
- 游客当前信任度（trust）、情绪（mood）、不满点（concerns）、隐藏诉求是否已透露（hidden_revealed）；
- 完整对话转写（transcript）：看导游是否实质完成了本阶段目标、有无严重失误、
  游客有无明确表达离团/投诉/不再信任；
- 本阶段已展开轮数（stage_turns）仅作防呆参考，不作为推进依据。

只输出一个 JSON 对象，不要任何多余文字：
{"action": "continue"|"advance"|"complete"|"fail", "reason": "20-60 字中文判定理由"}"""

_VALID_ACTIONS = ("continue", "advance", "complete", "fail")

# 兜底轮数上限（与 SandboxStage.max_turns 默认值 8 一致，防呆）
_FALLBACK_MAX_TURNS = 8

# 动作对应的默认中文理由（LLM 未给出 reason 时的兜底）
_DEFAULT_REASONS = {
    "fail": "游客信任已崩塌（信任度 {trust}），游客明确表达离团/投诉意愿，场景判定失败。",
    "complete": "所有阶段关键目标均已达成，游客对服务满意，场景圆满结束。",
    "advance": "本阶段关键目标已达成，剧情推进至下一阶段。",
    "continue": "本阶段关键目标尚未达成，对话继续展开。",
}


@dataclass(frozen=True)
class SceneDecision:
    """场景导演的一次判定结果。"""

    action: str  # "continue" | "advance" | "complete" | "fail"
    reason: str  # 中文判定理由（20-60 字，供前端/评估展示）
    outcome: str | None  # fail 时必填 "failed"；complete 时 "success"；其余 None


def _to_trust(customer_state: dict[str, Any]) -> int:
    """稳健读取信任度（0-100），非法值回退 60。"""
    try:
        return max(0, min(100, int(float(customer_state.get("trust", 60)))))
    except (TypeError, ValueError):
        return 60


def _to_decision(action: str, reason: str, trust: int) -> SceneDecision:
    """把规范化后的 action/reason 转成 SceneDecision（outcome 按规则赋值）。"""
    reason = (reason or "").strip()
    if action == "fail":
        return SceneDecision(
            action="fail",
            reason=reason or _DEFAULT_REASONS["fail"].format(trust=trust),
            outcome="failed",
        )
    if action == "complete":
        return SceneDecision(
            action="complete",
            reason=reason or _DEFAULT_REASONS["complete"],
            outcome="success",
        )
    if action == "advance":
        return SceneDecision(
            action="advance",
            reason=reason or _DEFAULT_REASONS["advance"],
            outcome=None,
        )
    return SceneDecision(
        action="continue",
        reason=reason or _DEFAULT_REASONS["continue"],
        outcome=None,
    )


def _fallback(trust: int, stage_turns: int) -> SceneDecision:
    """LLM 输出解析失败时的代码兜底：永远不抛异常。"""
    if trust < 20:
        return _to_decision("fail", "", trust)
    if stage_turns >= _FALLBACK_MAX_TURNS:
        return _to_decision("advance", "", trust)
    return _to_decision("continue", "", trust)


def _build_user_prompt(
    template: SandboxTemplate,
    stage_idx: int,
    customer: CustomerProfile,
    customer_state: dict[str, Any],
    transcript: str,
    stage_turns: int,
) -> str:
    """组装判定输入（模板/阶段/游客/心理状态/转写/轮数）。"""
    stage = template.stages[stage_idx]
    is_last = stage_idx >= len(template.stages) - 1
    trust = _to_trust(customer_state)
    concerns = customer_state.get("concerns") or []
    concerns_text = "、".join(str(c) for c in concerns) if concerns else "暂无"
    return (
        f"【场景】{template.title}（模式：{template.mode}）\n"
        f"【当前阶段】第 {stage_idx + 1}/{len(template.stages)} 阶段：{stage.title}\n"
        f"本阶段目标（objective）：{stage.objective}\n"
        f"是否为最后阶段：{'是' if is_last else '否'}\n\n"
        f"【游客】{customer.name}（{customer.nationality}，{customer.age} 岁）\n"
        f"性格：{customer.personality}\n偏好：{customer.preferences}\n\n"
        f"【游客当前状态】信任度：{trust}/100，情绪：{customer_state.get('mood', '一般')}，"
        f"不满/疑虑：{concerns_text}，隐藏诉求已透露：{customer_state.get('hidden_revealed', False)}\n\n"
        f"【完整对话转写】\n{transcript or '（对话刚开始，尚无内容）'}\n\n"
        f"【本阶段已展开轮数】{stage_turns}（仅防呆参考，不作为推进依据）\n\n"
        "请按 system 判定规则输出 JSON。"
    )


class SceneDirectorAgent(BaseAgent):
    """场景导演：判定沙盒场景是继续、推进、成功结束还是失败结束。"""

    agent_id = AgentId.SCENE_DIRECTOR

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)

    def run(self, **kwargs: Any) -> SceneDecision:
        """满足 BaseAgent 抽象方法；kwargs 转发到 decide。"""
        return self.decide(
            template=kwargs.get("template"),
            stage_idx=int(kwargs.get("stage_idx", 0)),
            customer=kwargs.get("customer"),
            customer_state=dict(kwargs.get("customer_state") or {}),
            transcript=str(kwargs.get("transcript", "")),
            stage_turns=int(kwargs.get("stage_turns", 0)),
        )

    def decide(
        self,
        template: SandboxTemplate,
        stage_idx: int,  # 当前阶段下标
        customer: CustomerProfile,
        customer_state: dict,  # {"trust": int, "mood": str, "concerns": list, "hidden_revealed": bool}
        transcript: str,  # 完整对话转写（含最近几轮）
        stage_turns: int,  # 当前阶段已展开轮数
    ) -> SceneDecision:
        """判定场景走向。

        优先信任 LLM 判定；任何解析失败（非法 JSON / 非法 action / LLM 异常）
        都落入代码兜底（trust<20 → fail；stage_turns>=8 → advance；否则 continue），
        本方法永远不抛异常。
        """
        trust = _to_trust(customer_state)
        try:
            data = self._call_llm_json(
                SCENE_DIRECTOR_SYSTEM_PROMPT,
                _build_user_prompt(template, stage_idx, customer, customer_state, transcript, stage_turns),
                max_tokens=256,
                temperature=0.2,
            )
            action = str(data.get("action") or "").strip()
            reason = str(data.get("reason") or "").strip()
            if action not in _VALID_ACTIONS:
                raise ValueError(f"无效的场景判定 action: {action!r}")
            # 防御性规整：判定规则要求「非最后阶段 → advance」，LLM 误判 complete 时规整
            if action == "complete" and stage_idx < len(template.stages) - 1:
                action = "advance"
            return _to_decision(action, reason, trust)
        except Exception:
            return _fallback(trust, stage_turns)
