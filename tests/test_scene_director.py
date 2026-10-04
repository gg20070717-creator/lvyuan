import json
from unittest.mock import MagicMock

from brain_of_cloud.domain.models import AgentConfig, AgentId
from brain_of_cloud.llm.client import LLMClient, LLMResponse
from brain_of_cloud.services.agents.base import BaseAgent
from brain_of_cloud.services.sandbox import (
    CustomerProfile,
    SandboxStage,
    SandboxTemplate,
)
from brain_of_cloud.services.scene_director import SceneDecision, SceneDirectorAgent


# ── fixtures ──


def _make_mock_llm(content: str = "mock response") -> LLMClient:
    """Create an LLMClient that returns canned responses without real API calls."""
    mock_response = LLMResponse(content=content, usage_tokens={"total_tokens": 10})
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = mock_response
    llm.model = "deepseek-v4-pro"
    return llm


def _make_customer() -> CustomerProfile:
    return CustomerProfile(
        name="王阿姨",
        nationality="中国",
        age="45",
        personality="随和",
        preferences="喜欢听历史故事",
        quirks="说话直来直去",
        hidden="希望导游多讲当地故事",
    )


def _make_template(n_stages: int = 3) -> SandboxTemplate:
    stages = [
        SandboxStage(
            title=f"阶段{i + 1}",
            objective=f"本阶段目标{i + 1}",
            guide_hint="提示",
            min_turns=2,
            max_turns=8,
        )
        for i in range(n_stages)
    ]
    return SandboxTemplate(
        template_id="t_test",
        mode="scenario",
        title="测试场景",
        location="测试地点",
        task="测试任务",
        difficulty=1,
        category="测试",
        opening="开场情境",
        stages=stages,
        goals=[("表达能力", 0.5), ("服务意识", 0.5)],
        customer_pool=[_make_customer()],
    )


def _make_state(trust: int = 60, mood: str = "一般", concerns: list | None = None, hidden_revealed: bool = False) -> dict:
    return {
        "trust": trust,
        "mood": mood,
        "concerns": concerns or [],
        "hidden_revealed": hidden_revealed,
    }


def _make_agent(llm: LLMClient, max_retries: int = 0) -> SceneDirectorAgent:
    config = AgentConfig(agent_id=AgentId.SCENE_DIRECTOR, role_group="test", max_retries=max_retries)
    return SceneDirectorAgent(llm_client=llm, config=config)


def _decide_json(action: str, reason: str = "判定理由内容充足超过二十字。") -> str:
    return json.dumps({"action": action, "reason": reason}, ensure_ascii=False)


# ── agent_id ──


class TestSceneDirectorAgentId:
    def test_agent_id_member_exists(self):
        assert AgentId.SCENE_DIRECTOR == "scene_director"
        assert AgentId.SCENE_DIRECTOR in AgentId

    def test_agent_class_uses_enum(self):
        assert SceneDirectorAgent.agent_id == AgentId.SCENE_DIRECTOR

    def test_is_baseagent_subclass(self):
        llm = _make_mock_llm(_decide_json("continue"))
        agent = _make_agent(llm)
        assert isinstance(agent, BaseAgent)
        assert isinstance(agent, SceneDirectorAgent)


# ── complete / success ──


class TestSceneDirectorComplete:
    def test_complete_last_stage_success(self):
        llm = _make_mock_llm(
            _decide_json("complete", "全部阶段目标已达成，游客对服务十分满意，场景圆满结束。")
        )
        agent = _make_agent(llm)
        template = _make_template(n_stages=3)
        decision = agent.decide(
            template=template,
            stage_idx=2,  # 最后阶段
            customer=_make_customer(),
            customer_state=_make_state(trust=85, mood="满意"),
            transcript="导游：……\n游客：谢谢你的讲解！",
            stage_turns=5,
        )

        assert isinstance(decision, SceneDecision)
        assert decision.action == "complete"
        assert decision.outcome == "success"
        assert decision.reason

    def test_complete_reason_preserved(self):
        reason = "所有阶段关键目标已达成，游客全程满意，无任何投诉。"
        llm = _make_mock_llm(_decide_json("complete", reason))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=1),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=90),
            transcript="",
            stage_turns=4,
        )
        assert decision.action == "complete"
        assert decision.reason == reason

    def test_complete_non_last_stage_normalized_to_advance(self):
        # 防御性规整：非最后阶段不可能 complete，按判定规则降为 advance
        llm = _make_mock_llm(
            _decide_json("complete", "本阶段目标达成。")
        )
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=80),
            transcript="",
            stage_turns=4,
        )
        assert decision.action == "advance"
        assert decision.outcome is None

    def test_complete_empty_reason_gets_default(self):
        llm = _make_mock_llm(_decide_json("complete", ""))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=1),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=88),
            transcript="",
            stage_turns=3,
        )
        assert decision.action == "complete"
        assert decision.outcome == "success"
        assert decision.reason


# ── fail / failed ──


class TestSceneDirectorFail:
    def test_fail_outcome_failed(self):
        llm = _make_mock_llm(
            _decide_json("fail", "游客信任彻底崩塌，明确表示要找旅行社投诉并离团。")
        )
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=10, mood="愤怒", concerns=["要投诉"]),
            transcript="游客：我要投诉你！这团我不带了！",
            stage_turns=3,
        )

        assert decision.action == "fail"
        assert decision.outcome == "failed"

    def test_fail_reason_preserved(self):
        reason = "导游辱骂游客并拒绝继续服务，违反服务规范，判定失败。"
        llm = _make_mock_llm(_decide_json("fail", reason))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=1,
            customer=_make_customer(),
            customer_state=_make_state(trust=30),
            transcript="",
            stage_turns=2,
        )
        assert decision.action == "fail"
        assert decision.outcome == "failed"
        assert decision.reason == reason

    def test_fail_empty_reason_includes_trust(self):
        llm = _make_mock_llm(_decide_json("fail", ""))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=10),
            transcript="",
            stage_turns=1,
        )
        assert decision.action == "fail"
        assert decision.outcome == "failed"
        assert "信任度 10" in decision.reason


# ── advance ──


class TestSceneDirectorAdvance:
    def test_advance_outcome_none(self):
        llm = _make_mock_llm(_decide_json("advance", "本阶段目标已达成，游客愿意继续行程，推进下一阶段。"))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=1,
            customer=_make_customer(),
            customer_state=_make_state(trust=72, mood="满意"),
            transcript="游客：好的，听你的安排。",
            stage_turns=6,
        )

        assert decision.action == "advance"
        assert decision.outcome is None


# ── continue ──


class TestSceneDirectorContinue:
    def test_continue_outcome_none(self):
        llm = _make_mock_llm(_decide_json("continue", "本阶段目标尚未达成，对话继续展开。"))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=55, mood="一般"),
            transcript="游客：嗯，然后呢？",
            stage_turns=2,
        )

        assert decision.action == "continue"
        assert decision.outcome is None


# ── LLM 输出解析失败兜底（永远不抛异常）──


class TestSceneDirectorFallback:
    def test_invalid_json_low_trust_fail(self):
        llm = _make_mock_llm(content="这不是合法 JSON {{{")
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=10),
            transcript="",
            stage_turns=1,
        )
        assert decision.action == "fail"
        assert decision.outcome == "failed"

    def test_invalid_json_many_turns_advance(self):
        llm = _make_mock_llm(content="not json")
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=60),
            transcript="",
            stage_turns=9,  # 超防呆上限
        )
        assert decision.action == "advance"
        assert decision.outcome is None

    def test_invalid_json_default_continue(self):
        llm = _make_mock_llm(content="not json")
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=60),
            transcript="",
            stage_turns=2,
        )
        assert decision.action == "continue"
        assert decision.outcome is None

    def test_missing_action_key_falls_back_to_continue(self):
        llm = _make_mock_llm(content=json.dumps({"reason": "只有理由没有 action"}))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=60),
            transcript="",
            stage_turns=2,
        )
        assert decision.action == "continue"
        assert decision.outcome is None

    def test_invalid_action_value_falls_back(self):
        llm = _make_mock_llm(content=json.dumps({"action": "snooze", "reason": "非法动作"}))
        decision = _make_agent(llm).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=60),
            transcript="",
            stage_turns=2,
        )
        assert decision.action == "continue"
        assert decision.outcome is None

    def test_llm_raise_never_propagates(self):
        llm = _make_mock_llm()
        llm.chat.side_effect = RuntimeError("LLM 服务不可用")
        decision = _make_agent(llm, max_retries=0).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=60),
            transcript="",
            stage_turns=1,
        )
        assert isinstance(decision, SceneDecision)
        assert decision.action == "continue"
        assert decision.outcome is None

    def test_llm_raise_low_trust_fail(self):
        llm = _make_mock_llm()
        llm.chat.side_effect = RuntimeError("LLM 服务不可用")
        decision = _make_agent(llm, max_retries=0).decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=5),
            transcript="",
            stage_turns=1,
        )
        assert decision.action == "fail"
        assert decision.outcome == "failed"


# ── 输入传递与数据类 ──


class TestSceneDirectorInputs:
    def test_inputs_passed_to_llm(self):
        llm = _make_mock_llm(_decide_json("continue"))
        agent = _make_agent(llm)
        template = _make_template(n_stages=3)
        agent.decide(
            template=template,
            stage_idx=1,
            customer=_make_customer(),
            customer_state=_make_state(trust=66, mood="一般", concerns=["讲解太赶"]),
            transcript="导游：欢迎来到古镇。\n游客：你好。",
            stage_turns=3,
        )
        call_args = llm.chat.call_args
        system = call_args[1]["system"]
        user_content = call_args[0][0][0]["content"]

        assert "场景导演" in system
        assert "测试场景" in user_content
        assert "本阶段目标2" in user_content
        assert "第 2/3 阶段" in user_content
        assert "王阿姨" in user_content
        assert "66/100" in user_content
        assert "讲解太赶" in user_content
        assert "欢迎来到古镇" in user_content
        assert "3" in user_content  # stage_turns

    def test_scene_decision_is_frozen_dataclass(self):
        decision = SceneDecision(action="continue", reason="继续对话", outcome=None)
        assert decision.action == "continue"
        assert decision.reason == "继续对话"
        assert decision.outcome is None
        try:
            decision.action = "advance"
            frozen = False
        except Exception:
            frozen = True
        assert frozen

    def test_default_construction_without_config(self):
        llm = _make_mock_llm(_decide_json("continue"))
        agent = SceneDirectorAgent(llm_client=llm)
        decision = agent.decide(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=60),
            transcript="",
            stage_turns=1,
        )
        assert decision.action == "continue"

    def test_run_delegates_to_decide(self):
        llm = _make_mock_llm(_decide_json("advance", "目标达成，推进。"))
        agent = _make_agent(llm)
        decision = agent.run(
            template=_make_template(n_stages=3),
            stage_idx=0,
            customer=_make_customer(),
            customer_state=_make_state(trust=70),
            transcript="",
            stage_turns=5,
        )
        assert decision.action == "advance"
        assert decision.outcome is None
