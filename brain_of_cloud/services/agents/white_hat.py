from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, Evidence
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent


WHITE_HAT_SYSTEM_PROMPT = """\
你是多智能体训练材料审查系统的白帽事实核查员。

任务：将生成的训练材料与提供的参考证据进行比对，判定材料是否「无虚假、无矛盾」。
对材料中每个事实性声称，对照证据验证，并分为三类：
- 已验证：与证据一致
- 矛盾：与证据冲突（这是必须指出的问题）
- 演绎：证据中没有直接写明，但属于合理的教学演绎——举例、类比、打比方、
  用自己的话讲解转化、个性化表达、基于证据的合理扩展。**演绎不是问题**，
  只要不与证据矛盾、不引入虚假事实，就不能作为「不通过」的理由。
- 待核验：无证据支撑且属于关键事实性声称（具体数字、法规条文、专有名词、
  流程步骤），无法判断真伪——如实标注，交由蓝帽综合判断，不单独判不通过。

判定标准（铁律）：
- 只有出现「矛盾」或「明显虚假」时才判「不通过」。
- 「演绎」内容必须放行：内容与书上原文不一致 ≠ 错误，讲解转化正是教学所需。
- 「待核验」项列出即可，提醒注意，不直接判不通过。

输出中文。以"白帽事实核查："开头，后跟判定（通过 或 不通过）。
逐条列出验证结果：声称 → 类别（已验证/矛盾/演绎/待核验）→ 说明。
严谨公正。你的职责是防止幻觉（虚假与矛盾），而非批评文风，更不是要求照搬原文。"""


class WhiteHatAgent(BaseAgent):
    agent_id = AgentId.WHITE_HAT

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
        evidence_text = ""
        if evidence:
            evidence_text = (
                "参考证据:\n"
                + "\n".join(
                    f"- [{item.chunk_id}] {item.content} (来源: {item.source})"
                    for item in evidence
                )
            )
        else:
            evidence_text = "未提供参考证据——所有声称默认为未验证。"

        user_prompt = (
            f"待事实核查的训练材料:\n\n{training_content[:3000]}\n\n"
            f"{evidence_text}\n\n"
            f"请逐一核验每个事实声称。输出白帽审查结果。"
        )

        review = self._call_llm(WHITE_HAT_SYSTEM_PROMPT, user_prompt, max_tokens=1024)
        is_failing = "不通过" in review
        return AgentResult(
            content=review,
            passed=not is_failing,
            metadata={"role": "white_hat"},
        )
