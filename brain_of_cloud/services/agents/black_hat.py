from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, Evidence
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent


BLACK_HAT_SYSTEM_PROMPT = """\
你是多智能体训练材料审查系统的黑帽逻辑审计员。这是核心反幻觉角色。

任务：识别入境游地陪导游训练材料中的逻辑错误、推理缺陷、误导内容、合规问题和专业标准违反。

重点检查：
1. 材料内部的逻辑矛盾
2. 可能误导或混淆学员的建议
3. 违反导游专业标准或安全规程
4. 流程中缺失的关键步骤
5. 模糊不清可能导致实际出错的指导

判定标准（铁律）：
- 判定依据是逻辑与规范，不是「与参考原文一致」。
- 允许合理的教学演绎：举例、类比、打比方、个性化表达、用自己的话讲解转化，
  只要不引入逻辑错误、不违背行业规范，就不能作为「不通过」的理由。
- 内容与原文不一致 ≠ 错误；只有逻辑错误、误导、违规、缺关键步骤才算问题。

输出中文。以"黑帽逻辑审计："开头，后跟判定（通过 或 不通过）。
列出每个发现的问题，标注严重程度（严重/中等/轻微），并给出具体修改建议。
判定"通过"意味着未发现严重或重大问题。轻微建议可以与通过共存。"""


class BlackHatAgent(BaseAgent):
    agent_id = AgentId.BLACK_HAT

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        effective_config = config or AgentConfig(
            agent_id=AgentId.BLACK_HAT,
            role_group="detection",
            reasoning_effort=80,
            system_prompt=BLACK_HAT_SYSTEM_PROMPT,
        )
        super().__init__(llm_client, effective_config)

    def run(
        self,
        training_content: str,
        evidence: list[Evidence] | None = None,
        learner_profile: object | None = None,
    ) -> AgentResult:
        user_prompt = (
            f"待审计的训练材料:\n\n{training_content[:3000]}\n\n"
            f"请执行严格的黑帽逻辑审计。做最严厉的批评者——宁可严格把关，不可虚报通过。"
        )

        review = self._call_llm(BLACK_HAT_SYSTEM_PROMPT, user_prompt, max_tokens=1024)
        is_failing = "不通过" in review
        return AgentResult(
            content=review,
            passed=not is_failing,
            metadata={"role": "black_hat"},
        )
