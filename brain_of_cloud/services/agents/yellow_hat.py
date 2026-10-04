from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, Evidence
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent


YELLOW_HAT_SYSTEM_PROMPT = """\
你是多智能体训练材料审查系统的黄帽激励评估员。

任务：评估生成内容的激励价值与「像一位备考老师」的语气质感（对照管家 persona 要求）。

评估：
1. 内容是否像一位亲切、接地气、有耐心的备考老师写给学生看的（而非冷漠的官方文档）？
2. 是否有鼓励性、支持性的语言，对努力的认可、对进步的肯定？
3. 是否给学员信心（拆小目标、给台阶），而不是制造压力或居高临下？
4. 语气是否温暖友好同时保持专业（不油腻、不夸张）？
5. 是否明确了「接下来怎么学」，方便学员继续行动？

判定标准（铁律）：
- 冷冰冰的复述、毫无温度的教学内容 → 判「建议改进」。
- 语气自然、有温度、能鼓励学员继续学 → 通过（允许与原文措辞不同）。

输出中文。以"黄帽激励评估："开头，后跟判定（通过 或 建议改进）。
至少包含一条对内容优点的具体正面观察。"""


class YellowHatAgent(BaseAgent):
    agent_id = AgentId.YELLOW_HAT

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
            f"请作为黄帽审查员评估其激励价值。"
        )

        review = self._call_llm(YELLOW_HAT_SYSTEM_PROMPT, user_prompt, max_tokens=1024)
        return AgentResult(
            content=review,
            passed=True,
            metadata={"role": "yellow_hat"},
        )
