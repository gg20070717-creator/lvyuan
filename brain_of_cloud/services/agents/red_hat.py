from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, Evidence, LearnerProfile
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent


RED_HAT_SYSTEM_PROMPT = """\
你是多智能体训练材料审查系统的红帽个性化与上下文适配检查员。

任务：检查生成内容是否匹配学员的画像（难度/风格/背景）与**当前教学上下文**
（正在教的主题、教学阶段、学员水平——对照管家的「上下文可见」要求）。

评估：
1. 难度级别是否适合学习者的当前水平（intro/basic/advanced/comprehensive）？
2. 语言风格是否符合学习者的偏好（如实操导向 vs 理论导向）？
3. 内容是否围绕学员**正在学/刚学的教学主题**展开，而不是答非所问或跑题？
4. 示例和场景是否与学习者的目标岗位相关？
5. 对水平低的学习者是否做了「降维解释」（大白话、拆步骤）？

输出中文。以"红帽个性适配："开头，后跟判定（通过 或 需调整）。
如果需调整，明确指出哪些方面需要改变以及如何改变。"""


class RedHatAgent(BaseAgent):
    agent_id = AgentId.RED_HAT

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)

    def run(
        self,
        training_content: str,
        evidence: list[Evidence] | None = None,
        learner_profile: LearnerProfile | None = None,
        teaching_context: str | None = None,
    ) -> AgentResult:
        profile_text = "未提供学员画像——无法执行个性化检查。"
        if learner_profile:
            profile_text = (
                f"学员画像:\n"
                f"- 背景: {learner_profile.background}\n"
                f"- 目标岗位: {learner_profile.target_role}\n"
                f"- 当前等级: {learner_profile.current_level}\n"
                f"- 风格偏好: {learner_profile.style_preferences}\n"
                f"- 基础评分: {learner_profile.baseline_scores}\n"
            )
        ctx_text = ""
        if teaching_context:
            ctx_text = f"教学上下文（内容应围绕它展开，答非所问 = 需调整）:\n{teaching_context}\n"

        user_prompt = (
            f"待评估的训练材料:\n\n{training_content[:3000]}\n\n"
            f"{profile_text}"
            f"{ctx_text}\n\n"
            f"请检查材料是否针对该学员进行了个性化与上下文适配。"
        )

        review = self._call_llm(RED_HAT_SYSTEM_PROMPT, user_prompt, max_tokens=1024)
        is_adjusted = "需调整" in review
        return AgentResult(
            content=review,
            passed=not is_adjusted,
            metadata={"role": "red_hat"},
        )
