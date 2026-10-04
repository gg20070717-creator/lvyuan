from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from brain_of_cloud.domain.models import AgentConfig, AgentId
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import BaseAgent


ESSAY_QUESTION_SYSTEM_PROMPT = """\
你是导游资格证培训的简答出题官。根据学员正在学的知识点与讲解内容，出一道有深度的简答题并给出参考答案要点。题目要贴合考试风格、有区分度，rubric 给出得分要点。"""

ESSAY_GRADE_SYSTEM_PROMPT = """\
你是导游资格证培训的阅卷老师，判分要宽松鼓励：学员答案覆盖 rubric 的主要要点（约一半以上）
就给 0.8 以上；遗漏个别细节最多扣 0.1-0.2；只有答案空泛、偏题或完全没答到要点才给 0.6 以下。
反馈用中文，先肯定答对的部分，再补充遗漏要点，2-3 句。只输出合法 JSON，格式：
{"score": 0.0-1.0, "feedback": "中文反馈（指出对错+补充要点，2-3 句）"}"""


@dataclass
class EssayQuestion:
    question_id: str
    knowledge_point_id: str
    prompt: str
    rubric: str


class EssayQuestionAgent(BaseAgent):
    agent_id = AgentId.ESSAY_QUESTION

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)

    def run(self, **kwargs) -> EssayQuestion:
        """满足 BaseAgent 抽象方法；kwargs 转发到 generate。"""
        return self.generate(
            kp_ids=list(kwargs.get("kp_ids", [])),
            topic_titles=list(kwargs.get("topic_titles", [])),
            context=str(kwargs.get("context", "")),
        )

    def generate(
        self,
        kp_ids: list[str],
        topic_titles: list[str],
        context: str,
    ) -> EssayQuestion:
        """根据教学主题知识点与最近讲解内容生成 1 道简答题（含参考答案要点 rubric）。

        LLM 输出须为 JSON {"prompt": "...", "rubric": "..."}；解析失败重试 1 次，
        仍失败返回兜底题目（不抛异常）。
        """
        question_id = f"essay_{uuid4().hex[:8]}"
        kp_id = kp_ids[0] if kp_ids else ""

        topic_text = "、".join(topic_titles) if topic_titles else "（未提供主题标题）"
        context_text = context.strip() if context and context.strip() else "（暂无讲解上下文）"
        kp_ids_text = "、".join(kp_ids) if kp_ids else "无"

        user_prompt = (
            f"学员当前学习的主题：{topic_text}\n"
            f"知识点 ID：{kp_id}（相关知识点：{kp_ids_text}）\n"
            f"最近讲解内容：\n{context_text}\n\n"
            f"请输出 1 道与该主题知识点紧密相关的简答题（导游证考试问答风格，开放式问答题，"
            f"如「请说明一五计划的历史背景及其意义」），rubric 给出 3-5 个参考答案要点。"
            f"只输出合法 JSON：{{\"prompt\": \"题目\", \"rubric\": \"参考答案要点\"}}"
        )

        for _ in range(2):
            try:
                data = self._call_llm_json(
                    ESSAY_QUESTION_SYSTEM_PROMPT,
                    user_prompt,
                    max_tokens=1024,
                )
                prompt = str(data["prompt"]).strip()
                rubric = str(data["rubric"]).strip()
                if prompt and rubric:
                    return EssayQuestion(
                        question_id=question_id,
                        knowledge_point_id=kp_id,
                        prompt=prompt,
                        rubric=rubric,
                    )
            except Exception:
                pass
            user_prompt += "\n\n上次输出不是合法 JSON，请只输出一个合法的 JSON 对象，不要任何其他内容。"

        return EssayQuestion(
            question_id=question_id,
            knowledge_point_id=kp_id,
            prompt="请结合刚才讲解的内容，谈谈你的理解。",
            rubric="无",
        )

    def grade(
        self,
        prompt: str,
        rubric: str,
        answer: str,
    ) -> tuple[bool, float, str]:
        """按 rubric 对学员简答作答进行 LLM 判分。

        LLM 输出须为 JSON {"score": 0.0-1.0, "feedback": "中文反馈"}；
        correct = score >= 0.7；解析失败兜底返回 (False, 0.0, 引导自查文案)。
        """
        user_prompt = (
            f"题目：{prompt}\n"
            f"参考答案要点（rubric）：{rubric}\n"
            f"学员答案：\n{answer}\n\n"
            f"请按 rubric 打分并给出中文反馈。只输出合法 JSON："
            f"{{\"score\": 0.0-1.0, \"feedback\": \"中文反馈（指出对错+补充要点，2-3 句）\"}}"
        )

        for _ in range(2):
            try:
                data = self._call_llm_json(
                    ESSAY_GRADE_SYSTEM_PROMPT,
                    user_prompt,
                    max_tokens=512,
                )
                score = float(data["score"])
                score = max(0.0, min(1.0, score))
                feedback = str(data["feedback"]).strip()
                if feedback:
                    return (score >= 0.7, score, feedback)
            except Exception:
                pass
            user_prompt += "\n\n上次输出不是合法 JSON，请只输出一个合法的 JSON 对象，不要任何其他内容。"

        return (False, 0.0, f"判分失败，请对照参考答案要点自查：{rubric[:80]}")
