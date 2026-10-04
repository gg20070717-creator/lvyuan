from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, Evidence
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent


GREEN_HAT_SYSTEM_PROMPT = """\
你是多智能体训练材料审查系统的绿帽创意与讲解转化评估员。

任务：评估生成内容是否达到「一对一老师讲解」的质量标准——既专业准确，又讲得像人话。

评估（对照管家的教学要求）：
1. **讲解转化**：内容是否用自己的话重新组织（有口语化表达、打比方、举例子、串场景），
   而不是照搬或大段复述知识库原文？照本宣科 = 不合格。
2. **教学演绎**：是否有生活化例子、类比、易错点提示等「老师在讲」的痕迹？
3. **吸引力**：是否像老师讲给学生听（有互动感、能让人读下去），而非干巴巴的文档堆砌？
4. **场景适配**：示例与场景是否贴合学员的目标岗位（导游带团/入境游接待/备考冲刺）？

判定标准（铁律）：
- 「与原文不一致」不是问题（讲解转化正是目标）；「只有原文没有讲解」才是问题。
- 内容完全复述原文、毫无演绎 → 判「建议改进」。

输出中文。以"绿帽创意评估："开头，后跟判定（通过 或 建议改进）。
即使通过，也请给出具体的讲解转化优化建议。"""


class GreenHatAgent(BaseAgent):
    agent_id = AgentId.GREEN_HAT

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
        learner_profile: object | None = None,
    ) -> AgentResult:
        user_prompt = (
            f"待评估的训练材料:\n\n{training_content[:3000]}\n\n"
            f"请作为绿帽审查员评估其创意性和新颖性。"
        )

        review = self._call_llm(GREEN_HAT_SYSTEM_PROMPT, user_prompt, max_tokens=1024)
        return AgentResult(
            content=review,
            passed=True,
            metadata={"role": "green_hat"},
        )
