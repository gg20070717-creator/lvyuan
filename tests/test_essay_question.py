import json
from unittest.mock import MagicMock

from brain_of_cloud.domain.models import AgentId
from brain_of_cloud.llm.client import LLMClient, LLMResponse
from brain_of_cloud.services.agents.essay_question import (
    EssayQuestion,
    EssayQuestionAgent,
)


def _make_mock_llm(content: str = "mock response") -> LLMClient:
    """Create an LLMClient that returns canned responses without real API calls."""
    mock_response = LLMResponse(content=content, usage_tokens={"total_tokens": 10})
    llm = MagicMock(spec=LLMClient)
    llm.chat.return_value = mock_response
    llm.model = "deepseek-v4-pro"
    return llm


def _make_agent(llm: LLMClient) -> EssayQuestionAgent:
    return EssayQuestionAgent(llm_client=llm)


class TestEssayQuestionAgentId:
    def test_agent_id_member_exists(self):
        assert AgentId.ESSAY_QUESTION == "essay_question"
        assert AgentId.ESSAY_QUESTION in AgentId

    def test_agent_class_uses_enum(self):
        assert EssayQuestionAgent.agent_id == AgentId.ESSAY_QUESTION


class TestEssayQuestionGenerate:
    def test_generate_returns_question_with_rubric(self):
        llm = _make_mock_llm(
            content=json.dumps(
                {
                    "prompt": "请说明一五计划的历史背景及其意义。",
                    "rubric": "1. 背景：建国初期工业基础薄弱；2. 借鉴苏联建设经验；3. 意义：初步奠定国家工业化基础。",
                },
                ensure_ascii=False,
            )
        )
        agent = _make_agent(llm)
        question = agent.generate(
            kp_ids=["kp_plan_5", "kp_industry"],
            topic_titles=["一五计划", "社会主义工业化"],
            context="今天我们讲了第一个五年计划的背景与意义……",
        )

        assert isinstance(question, EssayQuestion)
        assert question.question_id.startswith("essay_")
        assert len(question.question_id) == len("essay_") + 8
        assert question.knowledge_point_id == "kp_plan_5"
        assert question.prompt
        assert question.rubric
        # 输入上下文应传给 LLM
        call_args = llm.chat.call_args
        user_content = call_args[0][0][0]["content"]
        assert "一五计划" in user_content
        assert "kp_plan_5" in user_content

    def test_generate_fallback_on_invalid_json(self):
        llm = _make_mock_llm(content="这不是合法 JSON {{{")
        question = _make_agent(llm).generate(
            kp_ids=["kp_x"],
            topic_titles=["某主题"],
            context="",
        )

        assert question.question_id.startswith("essay_")
        assert question.knowledge_point_id == "kp_x"
        assert question.prompt == "请结合刚才讲解的内容，谈谈你的理解。"
        assert question.rubric == "无"

    def test_generate_empty_kp_ids(self):
        llm = _make_mock_llm(
            content=json.dumps(
                {"prompt": "请谈谈你的理解。", "rubric": "要点一；要点二"},
                ensure_ascii=False,
            )
        )
        question = _make_agent(llm).generate(
            kp_ids=[],
            topic_titles=[],
            context="",
        )

        assert question.question_id.startswith("essay_")
        assert question.knowledge_point_id == ""
        assert question.prompt
        assert question.rubric


class TestEssayQuestionGrade:
    def test_grade_high_score_is_correct(self):
        llm = _make_mock_llm(
            content=json.dumps(
                {
                    "score": 0.9,
                    "feedback": "回答正确，要点覆盖完整。补充：还可提到对后续工业布局的带动作用。",
                },
                ensure_ascii=False,
            )
        )
        correct, score, feedback = _make_agent(llm).grade(
            prompt="请说明一五计划的历史背景及其意义。",
            rubric="背景、借鉴苏联经验、意义",
            answer="一五计划是新中国第一个五年建设计划……",
        )

        assert correct is True
        assert score == 0.9
        assert feedback

    def test_grade_low_score_is_incorrect(self):
        llm = _make_mock_llm(
            content=json.dumps(
                {
                    "score": 0.3,
                    "feedback": "回答不完整，遗漏了历史背景这一关键要点。建议复习后再作答。",
                },
                ensure_ascii=False,
            )
        )
        correct, score, feedback = _make_agent(llm).grade(
            prompt="题目",
            rubric="要点",
            answer="不太确定",
        )

        assert correct is False
        assert score == 0.3
        assert feedback

    def test_grade_fallback_on_invalid_json(self):
        llm = _make_mock_llm(content="not json {{{")
        correct, score, feedback = _make_agent(llm).grade(
            prompt="题目",
            rubric="参考答案要点一二三四五六七八九十一二三四五六七八九十",
            answer="学员答案",
        )

        assert correct is False
        assert score == 0.0
        assert feedback.startswith("判分失败")
        assert "参考答案要点一二三四五六七八九十" in feedback
        # 兜底反馈只截取 rubric 前 80 字
        assert len(feedback) <= len("判分失败，请对照参考答案要点自查：") + 80
