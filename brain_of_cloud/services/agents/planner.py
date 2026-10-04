"""学习计划 Agent — 根据学员画像 + 掌握度缺口，生成个性化备考计划。"""

from __future__ import annotations

from typing import Any

from brain_of_cloud.domain.models import AgentConfig, AgentId, LearnerProfile
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import BaseAgent


PLANNER_SYSTEM_PROMPT = """\
你是导游资格证备考系统的学习规划师。

任务：根据学员的画像与当前学习状态，制定一份个性化、可执行的备考计划。

输入包含：
- 学员画像（背景 / 目标 / 等级 / 学习风格）
- 当前掌握情况（已掌握技能点 / 薄弱技能点 / 题库表现）
- 知识库结构（4 本教材：全国导游基础知识、导游业务、政策与法律法规、地方导游基础知识）

输出要求（中文）：
1. 【阶段目标】按时间/优先级分 2-3 个阶段
2. 【重点攻克】针对薄弱技能点，给出具体的复习顺序（引用技能点标题）
3. 【学习方法】结合学员学习风格，给出具体方法（如错题复盘、口诀记忆、情景演练）
4. 【每日建议】具体可执行的一天学习安排
5. 【自测安排】何时该去训练场做多少题

要具体到技能点，不要泛泛而谈。不要捏造学员没提供的信息。"""


class LearningPlannerAgent(BaseAgent):
    agent_id = AgentId.LEARNING_PLANNER

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)

    def run(
        self,
        *,
        user_id: str,
        profile: LearnerProfile | None = None,
        weak_points: list[str] | None = None,
        weak_point_titles: list[str] | None = None,
        mastered_count: int = 0,
        total_skills: int = 3796,
        recent_memories: list[dict[str, object]] | None = None,
    ) -> str:
        profile_text = self._profile_text(profile)
        weak_text = (
            "、".join(weak_point_titles or [])
            if weak_point_titles
            else "暂无已评测薄弱点（建议先做一套摸底测试）"
        )
        memory_lines = ""
        if recent_memories:
            memory_lines = "\n".join(
                f"- {m.get('content')}" for m in recent_memories[:8]
            )

        user_prompt = (
            f"学员ID: {user_id}\n"
            f"{profile_text}\n"
            f"当前进度：已掌握 {mastered_count}/{total_skills} 个技能点\n"
            f"薄弱技能点：{weak_text}\n"
            f"近期记忆：\n{memory_lines or '（无）'}\n\n"
            f"请为该学员制定个性化备考计划。"
        )
        return self._call_llm(
            PLANNER_SYSTEM_PROMPT,
            user_prompt,
            max_tokens=1024,
        )

    def _profile_text(self, profile: LearnerProfile | None) -> str:
        if profile is None:
            return "学员画像：尚未建立（建议先引导学员介绍背景）"
        return (
            f"学员画像：\n"
            f"- 背景: {profile.background or '未提供'}\n"
            f"- 目标: {profile.target_role or '未设定'}\n"
            f"- 等级: {profile.current_level or 'intro'}\n"
            f"- 学习风格: {profile.style_preferences or {}}"
        )
