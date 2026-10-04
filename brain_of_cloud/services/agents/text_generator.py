from __future__ import annotations

from brain_of_cloud.domain.models import AgentConfig, AgentId, LearnerProfile, Message
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import BaseAgent
from brain_of_cloud.services.agents.retrieval import RetrievalResult


TEXT_GENERATOR_SYSTEM_PROMPT = """\
你是入境游地陪导游训练系统的专业培训材料生成器。

任务：为接待外国游客的地陪导游生成高质量的中文训练材料。材料应该：
- 实用可操作（真实脚本、检查清单、步骤指南）
- 适合跨文化沟通场景
- 符合导游行业标准，专业准确
- 当有学习者画像时，根据其水平个性化调整

讲解转化铁律：
- 参考证据是「事实依据」不是「抄写模板」：必须用自己的话重新组织讲解，
  禁止大段照搬或复述检索原文。
- 允许并鼓励在证据基础上扩展演绎：打比方、举例子、编情景、串个人经验，
  只要不歪曲事实、不引入虚构数据。
- 内容是「讲给人听的」，不是「书本复印件」：先给结论，再展开要点，再给例子。

输出结构清晰，必须包含：
1. 训练场景标题
2. 目标技能或知识点
3. 具体示例、脚本或实操练习
4. 引用来源标注

输出中文。要具体，不要泛泛而谈。给出真正可用的脚本和流程。"""


class TextGeneratorAgent(BaseAgent):
    agent_id = AgentId.TEXT_GENERATOR

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)

    def run(
        self,
        user_message: Message,
        retrieval: RetrievalResult,
        learner_profile: LearnerProfile | None = None,
        previous_review_feedback: str | None = None,
        mastery_context: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        evidence_text = (
            "\n".join(
                f"- [{item.chunk_id}] {item.content} (来源: {item.source}, 可信度: {item.trust_score})"
                for item in retrieval.evidence
            )
            if retrieval.evidence
            else "无特定证据可用——基于通用导游最佳实践生成。"
        )

        profile_text = ""
        if learner_profile:
            profile_text = (
                f"\n\n学员画像:\n"
                f"- 背景: {learner_profile.background}\n"
                f"- 目标岗位: {learner_profile.target_role}\n"
                f"- 当前等级: {learner_profile.current_level}\n"
                f"- 学习风格: {learner_profile.style_preferences.get('mode', '未指定')}\n"
                f"- 基础评分: {learner_profile.baseline_scores}\n"
            )

        feedback_text = ""
        if previous_review_feedback:
            feedback_text = (
                f"\n\n重要——上一轮审查发现以下问题需要修改:\n"
                f"{previous_review_feedback}\n"
                f"请在修订版中解决上述所有问题。"
            )

        mastery_text = ""
        if mastery_context:
            mastery_text = f"\n\n{mastery_context}\n"

        user_prompt = (
            f"用户需求: {user_message.content}\n\n"
            f"参考证据:\n{evidence_text}"
            f"{profile_text}"
            f"{mastery_text}"
            f"{feedback_text}\n\n"
            f"请生成训练材料。"
        )

        content = self._call_llm(
            TEXT_GENERATOR_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=max_tokens if max_tokens is not None else 2048,
        )
        # 生成可能因推理模式返回空内容 — 重试一次，并明确要求直接输出正文
        if not content.strip():
            content = self._call_llm(
                TEXT_GENERATOR_SYSTEM_PROMPT + "\n\n直接输出材料正文，不要输出思考过程。",
                user_prompt,
                max_tokens=max_tokens if max_tokens is not None else 2048,
            )
        return content or "（本次生成未返回内容，请基于检索证据整理要点后再次尝试。）"