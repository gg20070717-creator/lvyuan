import json
from unittest.mock import MagicMock, patch

import pytest

from brain_of_cloud.domain.models import (
    AgentConfig,
    AgentId,
    Evidence,
    LearnerProfile,
    Message,
)
from brain_of_cloud.llm.client import LLMClient, LLMResponse
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents import (
    AgentResult,
    BlackHatAgent,
    BlueHatAgent,
    GreenHatAgent,
    ProfileAgent,
    RedHatAgent,
    RetrievalAgent,
    RetrievalResult,
    TextGeneratorAgent,
    TrainingAnalyzerAgent,
    WhiteHatAgent,
    YellowHatAgent,
)


def _make_mock_llm(content: str = "mock response") -> LLMClient:
    """Create an LLMClient that returns canned responses without real API calls."""
    mock_response = LLMResponse(content=content, usage_tokens={"total_tokens": 10})
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = mock_response
    llm.model = "deepseek-v4-pro"
    return llm


def _make_message(content: str = "请生成接待外国游客的地陪欢迎词训练材料。") -> Message:
    return Message(
        message_id="msg_test_1",
        task_id="task_test_1",
        from_agent=AgentId.CONCIERGE,
        content=content,
        lsn=1,
    )


def _make_evidence() -> list[Evidence]:
    return [
        Evidence(
            chunk_id="ev_welcome_script",
            content="欢迎词应先欢迎外国游客来到中国，介绍本人和司机，再说明当天行程、用餐安排、集合时间和安全提醒。",
            source="built-in:inbound-guide/welcome",
            trust_score=0.9,
            knowledge_point_ids=["kp_welcome"],
        ),
    ]


class TestConciergeAgentPersona:
    """管家不是「职责说明书」，而是有性格的带教者（问题1 修复的回归护栏）。"""

    def test_prompt_has_persona_and_style_rules(self):
        from brain_of_cloud.services.agents.concierge import CONCIERGE_SYSTEM_PROMPT

        # 人设：有名字、像老朋友
        assert "司南" in CONCIERGE_SYSTEM_PROMPT
        assert "陪考" in CONCIERGE_SYSTEM_PROMPT
        # 风格铁律：口语短句 / 禁用 AI 套话
        assert "口语短句" in CONCIERGE_SYSTEM_PROMPT
        assert "好的，我来帮你" in CONCIERGE_SYSTEM_PROMPT  # 明确禁止的套话
        # 交付规则：材料落为资产，聊天只给精华
        assert "学习中心" in CONCIERGE_SYSTEM_PROMPT
        assert "精华" in CONCIERGE_SYSTEM_PROMPT

    def test_config_uses_natural_tone_params(self):
        from brain_of_cloud.domain.models import AgentConfig, AgentId
        from brain_of_cloud.services.agents.concierge import ConciergeAgent

        llm = _make_mock_llm(content="你好呀")
        agent = ConciergeAgent(llm_client=llm)
        cfg = agent.config
        assert isinstance(cfg, AgentConfig)
        assert cfg.agent_id == AgentId.CONCIERGE
        # 对话/交付用更高温度；输出预算 2048 以容纳工具调用参数（如 evidence JSON，过小会被截断）
        assert cfg.temperature >= 0.8
        assert 1024 < cfg.max_tokens <= 2048

    def test_prompt_has_socratic_guidance_rules(self):
        """启发式导学：提问先判断是否适合引导，≤2 轮，学员可随时跳过（差距项 T3）。"""
        from brain_of_cloud.services.agents.concierge import CONCIERGE_SYSTEM_PROMPT

        assert "引导" in CONCIERGE_SYSTEM_PROMPT
        assert "直接告诉我答案" in CONCIERGE_SYSTEM_PROMPT
        # 追问轮次有上限
        assert "2" in CONCIERGE_SYSTEM_PROMPT


class TestBlueHatFiveDimReview:
    """蓝帽五维质量定标：输出结构化 5 维评分（差距项 T4）。"""

    def test_prompt_requires_five_dimension_scores(self):
        from brain_of_cloud.services.agents.blue_hat import BLUE_HAT_SYSTEM_PROMPT

        for dim in ("事实", "逻辑", "个性", "激励", "表达"):
            assert dim in BLUE_HAT_SYSTEM_PROMPT
        assert "1-5" in BLUE_HAT_SYSTEM_PROMPT or "1到5" in BLUE_HAT_SYSTEM_PROMPT


class TestRetrievalAgent:
    def test_delegates_to_plugin_and_returns_evidence(self):
        plugin = InboundGuidePlugin()
        llm = _make_mock_llm(
            content=json.dumps({
                "ranked_evidence": [
                    {
                        "chunk_id": "ev_welcome_script",
                        "relevance_reason": "Directly matches welcome script query",
                        "relevance_score": 0.95,
                    }
                ]
            })
        )
        agent = RetrievalAgent(plugin=plugin, llm_client=llm)

        result = agent.run(query="请生成地陪欢迎词", top_k=3)

        assert isinstance(result, RetrievalResult)
        assert result.query == "请生成地陪欢迎词"
        assert len(result.evidence) > 0
        assert result.evidence[0].chunk_id == "ev_welcome_script"

    def test_returns_raw_evidence_on_llm_error(self):
        plugin = InboundGuidePlugin()
        llm = _make_mock_llm(content="not valid json {{{")
        agent = RetrievalAgent(plugin=plugin, llm_client=llm)

        result = agent.run(query="欢迎词", top_k=3)

        assert len(result.evidence) > 0

    def test_gracefully_handles_low_relevance_query(self):
        plugin = InboundGuidePlugin()
        llm = _make_mock_llm(content=json.dumps({"ranked_evidence": []}))
        agent = RetrievalAgent(plugin=plugin, llm_client=llm)

        result = agent.run(query="zzz_nonexistent_xyzzy", top_k=3)

        assert len(result.evidence) <= 3


class TestTextGeneratorAgent:
    def test_returns_llm_generated_content(self):
        llm = _make_mock_llm(content="入境游地陪导游训练材料\n\n训练场景：在上海机场接待外国游客...")
        agent = TextGeneratorAgent(llm_client=llm)
        message = _make_message()
        evidence = _make_evidence()
        retrieval = RetrievalResult(query=message.content, evidence=evidence)

        result = agent.run(message, retrieval)

        assert "入境游" in result
        assert "地陪" in result

    def test_includes_learner_profile_when_provided(self):
        llm = _make_mock_llm(content="训练材料（适配入门级别）...")
        agent = TextGeneratorAgent(llm_client=llm)
        message = _make_message()
        retrieval = RetrievalResult(query=message.content, evidence=[])
        profile = LearnerProfile(
            user_id="user_1",
            background="旅游管理专业学生",
            target_role="入境游地陪导游",
            current_level="intro",
            style_preferences={"mode": "实操优先"},
        )

        result = agent.run(message, retrieval, learner_profile=profile)

        assert len(result) > 0
        # messages is passed as first positional arg to chat()
        call_args = llm.chat.call_args
        user_content = call_args[0][0][0]["content"]
        assert "旅游管理专业学生" in user_content
        assert "intro" in user_content

    def test_includes_previous_review_feedback(self):
        llm = _make_mock_llm(content="修正后的训练材料...")
        agent = TextGeneratorAgent(llm_client=llm)
        message = _make_message()
        retrieval = RetrievalResult(query=message.content, evidence=[])

        agent.run(
            message,
            retrieval,
            previous_review_feedback="缺少安全提醒部分",
        )

        call_args = llm.chat.call_args
        user_content = call_args[0][0][0]["content"]
        assert "安全提醒" in user_content
        assert "重要" in user_content


class TestBlueHatAgent:
    def test_review_contains_required_phrases(self):
        llm = _make_mock_llm(
            content="蓝帽检测：合格。所有维度均通过审核。事实准确、逻辑清晰、语言得体、内容完整、实用性强。"
        )
        agent = BlueHatAgent(llm_client=llm)

        result = agent.run(training_content="入境游地陪导游训练材料...")

        assert "蓝帽检测" in result
        assert "合格" in result

    def test_review_fails_when_content_has_issues(self):
        llm = _make_mock_llm(
            content="蓝帽检测：需修改。事实准确性不足，景点介绍缺少具体历史背景。建议补充文化背景说明。"
        )
        agent = BlueHatAgent(llm_client=llm)

        result = agent.run(training_content="incomplete material...")

        assert "蓝帽检测" in result
        assert "需修改" in result

    def test_coordinate_aggregates_hat_results(self):
        llm = _make_mock_llm(
            content="蓝帽检测：合格。综合5帽审查：白帽通过、黑帽通过、绿帽通过、黄帽通过、红帽通过。材料质量达标。"
        )
        agent = BlueHatAgent(llm_client=llm)
        hat_results = {
            AgentId.WHITE_HAT: AgentResult(content="事实核查通过", passed=True),
            AgentId.BLACK_HAT: AgentResult(content="逻辑审计通过", passed=True),
        }

        result = agent.coordinate("training content", hat_results)

        assert "蓝帽检测" in result
        assert "合格" in result


class TestWhiteHatAgent:
    def test_fact_check_passes_when_no_contradictions(self):
        llm = _make_mock_llm(content="白帽事实核查：通过。所有事实声称均已验证，未发现与证据矛盾的内容。")
        agent = WhiteHatAgent(llm_client=llm)
        evidence = _make_evidence()

        result = agent.run(training_content="欢迎词应包含问候、行程说明...", evidence=evidence)

        assert result.passed is True
        assert "白帽事实核查" in result.content

    def test_fact_check_fails_when_contradictions_found(self):
        llm = _make_mock_llm(content="白帽事实核查：不通过。发现2处矛盾：声称的集合时间与标准流程不符。")
        agent = WhiteHatAgent(llm_client=llm)

        result = agent.run(training_content="inaccurate claims...", evidence=_make_evidence())

        assert result.passed is False
        assert "不通过" in result.content


class TestBlackHatAgent:
    def test_logic_audit_passes_when_no_critical_issues(self):
        llm = _make_mock_llm(content="黑帽逻辑审计：通过。未发现严重逻辑错误。2个轻微建议已标注。")
        agent = BlackHatAgent(llm_client=llm)

        result = agent.run(training_content="logically sound training material...")

        assert result.passed is True
        assert "黑帽逻辑审计" in result.content

    def test_logic_audit_fails_when_critical_issues_found(self):
        llm = _make_mock_llm(content="黑帽逻辑审计：不通过。严重问题：安全流程步骤顺序错误，可能误导学员。")
        agent = BlackHatAgent(llm_client=llm)

        result = agent.run(training_content="flawed logic...")

        assert result.passed is False
        assert "不通过" in result.content
        assert "严重" in result.content


class TestGreenHatAgent:
    def test_creativity_assessment_returns_content(self):
        llm = _make_mock_llm(content="绿帽创意评估：通过。材料使用了具体的入境接待场景，有角色扮演练习建议。")
        agent = GreenHatAgent(llm_client=llm)

        result = agent.run(training_content="creative training material...")

        assert "绿帽创意评估" in result.content


class TestYellowHatAgent:
    def test_motivation_assessment_returns_content(self):
        llm = _make_mock_llm(content="黄帽激励评估：通过。材料语气温暖，使用了鼓励性语言，成功标准明确。")
        agent = YellowHatAgent(llm_client=llm)

        result = agent.run(training_content="motivational training material...")

        assert "黄帽激励评估" in result.content


class TestRedHatAgent:
    def test_personalization_passes_when_matching_profile(self):
        llm = _make_mock_llm(content="红帽个性适配：通过。材料难度匹配学习者入门级别，实操导向符合偏好。")
        agent = RedHatAgent(llm_client=llm)
        profile = LearnerProfile(
            user_id="user_1",
            background="旅游管理专业学生",
            target_role="入境游地陪导游",
            current_level="intro",
            style_preferences={"mode": "实操优先"},
        )

        result = agent.run(training_content="intro-level practical material...", learner_profile=profile)

        assert result.passed is True
        assert "红帽个性适配" in result.content

    def test_personalization_fails_when_mismatched(self):
        llm = _make_mock_llm(content="红帽个性适配：需调整。材料使用的专业术语过多，不适合入门级学习者。建议简化表达。")
        agent = RedHatAgent(llm_client=llm)
        profile = LearnerProfile(
            user_id="user_1",
            background="零基础",
            target_role="入境游地陪导游",
            current_level="intro",
        )

        result = agent.run(training_content="advanced jargon-heavy material...", learner_profile=profile)

        assert result.passed is False
        assert "需调整" in result.content


class TestTrainingAnalyzerAgent:
    def test_enriches_mastery_report_with_qualitative_analysis(self):
        from brain_of_cloud.services.training import TrainingService

        llm = _make_mock_llm(
            content="建议先强化接站流程中的行李确认和人数清点技能，再进入景点讲解的情景模拟训练。"
        )
        training = TrainingService(InboundGuidePlugin())
        training.submit("user_1", "q_welcome_1", "欢迎各位游客，我是导游，司机在门口等候，行程包括外滩，请注意集合安全")
        agent = TrainingAnalyzerAgent(llm_client=llm, training_service=training)

        report = agent.run(user_id="user_1")

        assert report.user_id == "user_1"
        assert len(report.recommended_action) > 0
        assert "景点" in report.recommended_action or "接站" in report.recommended_action


class TestProfileAgent:
    def test_generates_profile_from_background(self):
        llm = _make_mock_llm(
            content=(
                '{"background": "旅游管理专业大三学生，有导游证但无入境游经验", '
                '"target_role": "入境游地陪导游", '
                '"current_level": "intro", '
                '"style_preferences": {"mode": "实操优先"}, '
                '"baseline_scores": {"kp_welcome": 0.4, "kp_pickup": 0.3}}'
            )
        )
        agent = ProfileAgent(llm_client=llm)

        profile = agent.generate_profile(
            user_id="user_1",
            background="旅游管理专业大三学生，有导游证但无入境游经验",
        )

        assert profile.user_id == "user_1"
        assert profile.current_level == "intro"
        assert profile.style_preferences.get("mode") == "实操优先"

    def test_update_progress_tracks_consecutive_results(self):
        llm = _make_mock_llm()
        agent = ProfileAgent(llm_client=llm)

        r1 = agent.update_progress("user_1", "inbound_tour", "kp_welcome", 1.0, True)
        assert r1.consecutive_correct == 1
        assert r1.consecutive_incorrect == 0

        r2 = agent.update_progress("user_1", "inbound_tour", "kp_welcome", 1.0, True)
        assert r2.consecutive_correct == 2

        r3 = agent.update_progress("user_1", "inbound_tour", "kp_welcome", 0.0, False)
        assert r3.consecutive_correct == 0
        assert r3.consecutive_incorrect == 1

    def test_check_dynamic_thresholds_returns_advance(self):
        llm = _make_mock_llm()
        agent = ProfileAgent(llm_client=llm)

        for _ in range(3):
            agent.update_progress("user_1", "inbound_tour", "kp_welcome", 1.0, True)

        result = agent.check_dynamic_thresholds("user_1", "inbound_tour")
        assert result == "advance"

    def test_check_dynamic_thresholds_returns_downgrade(self):
        llm = _make_mock_llm()
        agent = ProfileAgent(llm_client=llm)

        for _ in range(3):
            agent.update_progress("user_1", "inbound_tour", "kp_welcome", 0.0, False)

        result = agent.check_dynamic_thresholds("user_1", "inbound_tour")
        assert result == "downgrade"

    def test_adjust_difficulty_levels(self):
        llm = _make_mock_llm()
        agent = ProfileAgent(llm_client=llm)

        for _ in range(2):
            agent.update_progress("user_1", "inbound_tour", "kp_welcome", 1.0, True)

        record = agent.update_progress("user_1", "inbound_tour", "kp_welcome", 1.0, True)
        assert record.difficulty == "basic"
