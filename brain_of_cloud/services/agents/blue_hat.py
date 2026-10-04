from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, Evidence
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent


BLUE_HAT_SYSTEM_PROMPT = """\
你是多智能体训练材料质量审查系统的蓝帽协调者。

任务：审查生成的入境游地陪导游训练材料，按五个维度分别打分（1-5 分）：
1. 事实准确（事实准确性——与知识库/行业规范**无矛盾、无虚构**；注意：允许合理的
   扩展演绎与个性化表达（举例、类比、讲解转化），**不等于要求与原文一致**）
2. 逻辑一致（逻辑一致性——流程是否清晰，有无前后矛盾）
3. 个性适配（个性适配——难度与风格是否匹配目标学员画像，红帽结论可参考）
4. 激励价值（激励价值——是否给学员正向反馈和学习动力）
5. 表达清晰（表达清晰——语言是否得体、易懂、适合跨文化场景）

判定铁律：
- 「与参考原文不一致」永远不是扣分理由；只有「与知识库/规范矛盾、虚构、
  逻辑错误、误导、违规」才是问题。
- 讲解转化、举例、个性化的表达是教学价值所在，应给高分而非扣分。

输出格式：
第一行：蓝帽检测：合格 或 需修改
第二行起：逐维度给出「维度名：N/5 — 一句话评价」
最后一行：综合结论与具体修改建议（需修改时必须给出可操作建议）。

全部维度 ≥3 分才可判合格；任一维度 ≤2 分必须判需修改。
严谨但建设性。宁可严格把关，不可虚报合格。"""


class BlueHatAgent(BaseAgent):
    agent_id = AgentId.BLUE_HAT

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
    ) -> str:
        evidence_text = ""
        if evidence:
            evidence_text = (
                "\n\n生成材料时使用的参考证据:\n"
                + "\n".join(
                    f"- [{item.chunk_id}] {item.content}"
                    for item in evidence
                )
            )

        user_prompt = (
            f"待审查的训练材料:\n\n{training_content}"
            f"{evidence_text}\n\n"
            f"请给出蓝帽质量审查。"
        )

        return self._call_llm(
            BLUE_HAT_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=1024,
        )

    def coordinate(
        self,
        training_content: str,
        hat_results: dict[AgentId, AgentResult],
    ) -> str:
        hat_summary = "\n".join(
            f"- {agent_id.value}: {'通过' if result.passed else '不通过' if result.passed is False else '中性'} — {result.content[:200]}"
            for agent_id, result in hat_results.items()
        )

        user_prompt = (
            f"训练材料:\n{training_content[:2000]}\n\n"
            f"各帽审查结果:\n{hat_summary}\n\n"
            f"作为蓝帽协调者，综合以上结果给出最终判定。"
            f"以'蓝帽检测：'开头，后跟 合格 或 需修改。"
            f"总结关键发现并给出统一建议。"
        )

        return self._call_llm(
            BLUE_HAT_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=1024,
        )
