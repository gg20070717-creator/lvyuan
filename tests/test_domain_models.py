import pytest
from pydantic import ValidationError

from brain_of_cloud.domain.models import (
    AgentConfig,
    AgentId,
    Evidence,
    LearnerProfile,
    Message,
    Mention,
    ProgressRecord,
    Visibility,
)


def test_mention_keeps_structured_agent_id_and_payload():
    mention = Mention(
        agent_id=AgentId.TEXT_GENERATOR,
        reason="generate_learning_resource",
        payload={"resource_type": "graded_quiz"},
    )

    assert mention.agent_id == AgentId.TEXT_GENERATOR
    assert mention.payload["resource_type"] == "graded_quiz"


def test_message_defaults_to_group_visibility_and_empty_mentions():
    message = Message(
        message_id="msg_1",
        task_id="task_1",
        from_agent=AgentId.CONCIERGE,
        content="Please generate a welcome script.",
        lsn=1,
    )

    assert message.visibility == Visibility.GROUP
    assert message.mentions == []


def test_models_reject_extra_fields():
    with pytest.raises(ValidationError):
        Mention(
            agent_id=AgentId.TEXT_GENERATOR,
            reason="generate_learning_resource",
            unexpected=True,
        )


def test_models_validate_numeric_bounds():
    with pytest.raises(ValidationError):
        Message(
            message_id="msg_1",
            task_id="task_1",
            from_agent=AgentId.CONCIERGE,
            content="Please generate a welcome script.",
            lsn=0,
        )

    with pytest.raises(ValidationError):
        Evidence(
            chunk_id="chunk_1",
            content="Welcome script evidence.",
            source="source",
            trust_score=1.1,
            knowledge_point_ids=["kp_1"],
        )


class TestLearnerProfile:
    def test_minimal_fields(self):
        profile = LearnerProfile(
            user_id="user_1",
            background="旅游管理专业学生",
            target_role="入境游地陪导游",
        )
        assert profile.user_id == "user_1"
        assert profile.current_level == "intro"
        assert profile.style_preferences == {}
        assert profile.baseline_scores == {}

    def test_full_fields(self):
        profile = LearnerProfile(
            user_id="user_2",
            background="国内导游转入境游",
            target_role="外语导游助理",
            current_level="basic",
            style_preferences={"mode": "实操优先"},
            baseline_scores={"kp_welcome": 0.5},
            created_at="2026-07-10T10:00:00",
            updated_at="2026-07-10T12:00:00",
        )
        assert profile.style_preferences["mode"] == "实操优先"
        assert profile.baseline_scores["kp_welcome"] == 0.5
        assert profile.updated_at == "2026-07-10T12:00:00"


class TestProgressRecord:
    def test_defaults(self):
        record = ProgressRecord(
            user_id="user_1",
            plugin_id="inbound_tour_local_guide",
            knowledge_point_id="kp_welcome",
            mastery=0.5,
        )
        assert record.attempt_count == 0
        assert record.consecutive_correct == 0
        assert record.consecutive_incorrect == 0
        assert record.difficulty == "intro"

    def test_rejects_mastery_out_of_range(self):
        with pytest.raises(ValidationError):
            ProgressRecord(
                user_id="user_1",
                plugin_id="p",
                knowledge_point_id="kp",
                mastery=1.5,
            )

    def test_rejects_negative_consecutive(self):
        with pytest.raises(ValidationError):
            ProgressRecord(
                user_id="user_1",
                plugin_id="p",
                knowledge_point_id="kp",
                mastery=0.5,
                consecutive_correct=-1,
            )


class TestAgentConfig:
    def test_defaults(self):
        config = AgentConfig(
            agent_id=AgentId.TEXT_GENERATOR,
            role_group="knowledge_generation",
        )
        assert config.model == "deepseek-v4-flash-vision-exp"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.max_retries == 3
        assert config.system_prompt == ""

    def test_all_agent_ids_are_configurable(self):
        for agent_id in AgentId:
            config = AgentConfig(
                agent_id=agent_id,
                role_group="test",
            )
            assert config.agent_id == agent_id
