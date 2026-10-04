from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, MasteryReport
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent
from brain_of_cloud.services.training import TrainingService


TRAINING_ANALYZER_SYSTEM_PROMPT = """\
你是多智能体入境游地陪导游训练系统的训练场分析师。

任务：分析训练结果，生成关于学员学习进展的定性分析。
根据包含各知识点得分的掌握度报告，产出丰富分析，包括：
1. 学习趋势解读（哪些领域有进步，哪些停滞）
2. 具体薄弱点原因解释（为什么这个知识点会有困难？）
3. 具体的下一步行动建议（非通用建议——要针对该学员的具体模式）

输出中文。要具体可操作。避免"继续练习"这样的通用建议。
应该说"建议先复习接站流程中的行李确认步骤，再进行景点讲解练习。"
"""


class TrainingAnalyzerAgent(BaseAgent):
    agent_id = AgentId.TRAINING_ANALYZER

    def __init__(
        self,
        llm_client: LLMClient,
        training_service: TrainingService,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)
        self._training = training_service

    def run(self, user_id: str) -> MasteryReport:
        base_report = self._training.get_mastery(user_id)

        point_details = "\n".join(
            f"- {kp_id}: 掌握度={score:.2f}"
            for kp_id, score in base_report.knowledge_point_scores.items()
        )
        weak_detail = (
            ", ".join(base_report.weak_points)
            if base_report.weak_points
            else "无薄弱点"
        )

        user_prompt = (
            f"掌握度报告摘要:\n"
            f"- 学员: {user_id}\n"
            f"- 知识点得分:\n{point_details}\n"
            f"- 薄弱点: {weak_detail}\n"
            f"- 当前建议: {base_report.recommended_action}\n\n"
            f"请生成定性分析和具体的下一步行动建议。"
        )

        analysis = self._call_llm(
            TRAINING_ANALYZER_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=512,
        )

        return MasteryReport(
            report_id=base_report.report_id,
            user_id=base_report.user_id,
            knowledge_point_scores=base_report.knowledge_point_scores,
            weak_points=base_report.weak_points,
            recommended_action=analysis,
        )

    def reteach_angle(
        self,
        user_id: str,
        question_id: str,
        answer: str,
        submission,
    ) -> str:
        """学员答错后，生成「换个角度重新讲解」的切入点建议（阅卷老师视角）。

        输入题目/答案/错因标签，输出一句 ≤60 字的重讲角度（生活化类比、
        易错点反讲、顺序重排等），供管家重讲时使用。
        """
        question = self._training.get_question(question_id)
        if question is None:
            return ""
        tags = "、".join(submission.misconception_tags) or "无"
        answer_key = question.answer_key or question.answer or ""
        prompt = (
            f"学员答错了一道导游资格证题目，需要你给出重讲切入点。\n"
            f"题目：{question.prompt}\n"
            f"标准答案要点：{answer_key}\n"
            f"题目解析：{question.explanation or '无'}\n"
            f"错因标签：{tags}\n"
            f"学员答案：{(answer or '')[:200]}\n\n"
            f"请给出一句「换个角度讲解」的切入点建议（生活化类比 / 易错点反讲 / "
            f"步骤顺序重排 任选一种），不超过 60 字，直接输出建议本身。"
        )
        try:
            return self._call_llm(
                "你是导游资格证培训的阅卷老师，擅长用通俗方式让学员真正理解错因。",
                prompt,
                max_tokens=120,
            ).strip()
        except Exception:
            return ""
