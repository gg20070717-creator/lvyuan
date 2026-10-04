from __future__ import annotations

import json

from brain_of_cloud.domain.models import (
    AgentConfig,
    AgentId,
    LearnerProfile,
    MasteryReport,
    ProgressRecord,
)
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.agents.base import AgentResult, BaseAgent


PROFILE_GENERATION_SYSTEM_PROMPT = """\
你是多智能体入境游地陪导游训练系统的个性画像生成器。

任务：根据用户提供的信息生成结构化学习者画像。输入可能包含三类信息：
1. 学员自述背景（最新）——用户当下对自己的描述；
2. 学情画像（先验问卷/系统画像）——已有结构化画像：目标岗位、基础档位、风格等；
3. 实测掌握度——用户在各技能点的真实答题/演练掌握度（为空说明尚无学习记录）。

输出以下JSON格式：
{
    "background": "学员教育/职业背景摘要（融合自述与学情画像，简洁）",
    "target_role": "训练目标岗位",
    "current_level": "intro|basic|advanced|comprehensive",
    "style_preferences": {"mode": "实操优先|理论优先|混合", "format": "文字|图表|情景演练"},
    "baseline_scores": {"kp_pickup": 0.0, "kp_welcome": 0.0, ...},
    "calibration_note": "一句话说明本次等级/基线如何综合自评与实测校准（可空）"
}

【校准规则】
- 有实测掌握度时：baseline_scores 尽量采用实测值；无实测的技能点可保留自评估算或留空。
- current_level 需综合三来源保守校准：
  自评或学情画像给了较高等级，但实测平均分/覆盖率明显偏低 → 下调一档；
  实测稳定且覆盖高（≥70 占比高）且自评不低 → 可维持或上调；
  经验不明确且无任何实测 → 默认 intro。
- 学情画像与最新自述冲突时，以最新自述为主，并在 calibration_note 说明差异。
- 保守评估——如果经验不明确则默认 intro。
"""



class ProfileAgent(BaseAgent):
    agent_id = AgentId.PROFILE

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        super().__init__(llm_client, config)
        self._profiles: dict[str, LearnerProfile] = {}
        self._records: dict[str, list[ProgressRecord]] = {}

    def run(self, **kwargs: object) -> AgentResult:
        action = kwargs.get("action", "generate_profile")
        if action == "generate_profile":
            profile = self.generate_profile(
                user_id=str(kwargs.get("user_id", "")),
                background=str(kwargs.get("background", "")),
                target_role=str(kwargs.get("target_role", "入境游地陪导游")),
                current_level=str(kwargs.get("current_level", "intro")),
                onboarding=kwargs.get("onboarding"),
                mastery=kwargs.get("mastery"),
            )
            return AgentResult(
                content=profile.model_dump_json(),
                passed=True,
                metadata={"action": "generate_profile"},
            )
        return AgentResult(content="unknown action", passed=None)

    def generate_profile(
        self,
        user_id: str,
        background: str,
        target_role: str = "入境游地陪导游",
        current_level: str = "intro",
        onboarding: dict | None = None,
        mastery: dict | None = None,
    ) -> LearnerProfile:
        ctx_lines = [
            f"学员ID: {user_id}",
            f"自述背景: {background}",
            f"目标岗位: {target_role}",
            f"自评等级: {current_level}",
        ]
        if onboarding:
            p0 = onboarding.get("persona") or onboarding
            summary = str(p0.get("summary") or p0.get("description") or "")
            goal = str(p0.get("goal") or "")
            basis = str(p0.get("basis") or "")
            label = str(p0.get("label") or "")
            gs = onboarding.get("group_status") or {}
            known = sum(1 for v in gs.values() if str(v).strip().lower() in ("known", "掌握", "100"))
            line = "【学情画像】"
            if goal:
                line += "目标=" + goal + "；"
            if basis:
                line += "基础=" + basis + "；"
            if label:
                line += "档位标签=" + label + "；"
            if summary:
                line += "概述=" + summary[:200]
            ctx_lines.append(line)
            if gs:
                ctx_lines.append(f"先验问卷已标记掌握分组 {known}/{len(gs)} 个。")
        if mastery:
            scores = mastery.get("scores") or {}
            vals: list[float] = []
            for _v in scores.values():
                try:
                    vals.append(float(_v))
                except (TypeError, ValueError):
                    continue
            avg = round(sum(vals) / len(vals), 1) if vals else 0.0
            mastered = sum(1 for v in vals if v >= 70)
            weak = list(mastery.get("weak_points") or [])[:6]
            ctx_lines.append(
                f"【实测掌握度】已产生掌握度技能点 {len(scores)} 个；平均 {avg:.1f}；"
                f"达到熟练(≥70) {mastered} 个；薄弱点 {'、'.join(str(w) for w in weak) if weak else '无'}。"
            )
        user_prompt = (
            "\n".join(ctx_lines)
            + "\n\n请生成结构化JSON学员画像（有学情/实测时须据此校准等级与基线）。"
        )

        try:
            data = self._call_llm_json(
                PROFILE_GENERATION_SYSTEM_PROMPT,
                user_prompt,
            )
        except (json.JSONDecodeError, Exception):
            data = {}

        profile = LearnerProfile(
            user_id=user_id,
            background=data.get("background", background),
            target_role=data.get("target_role", target_role),
            current_level=data.get("current_level", current_level),
            style_preferences=data.get("style_preferences", {}),
            baseline_scores=data.get("baseline_scores", {}),
        )
        self._profiles[user_id] = profile
        return profile

    def get_profile(self, user_id: str) -> LearnerProfile | None:
        return self._profiles.get(user_id)

    def update_progress(
        self,
        user_id: str,
        plugin_id: str,
        knowledge_point_id: str,
        score: float,
        correct: bool,
    ) -> ProgressRecord:
        key = f"{user_id}:{plugin_id}"
        records = self._records.setdefault(key, [])

        matching = [
            r for r in records if r.knowledge_point_id == knowledge_point_id
        ]
        current = matching[0] if matching else ProgressRecord(
            user_id=user_id,
            plugin_id=plugin_id,
            knowledge_point_id=knowledge_point_id,
            mastery=0.0,
            attempt_count=0,
            consecutive_correct=0,
            consecutive_incorrect=0,
            difficulty="intro",
        )

        new_attempt_count = current.attempt_count + 1
        if correct:
            new_consecutive_correct = current.consecutive_correct + 1
            new_consecutive_incorrect = 0
        else:
            new_consecutive_correct = 0
            new_consecutive_incorrect = current.consecutive_incorrect + 1

        new_mastery = (
            (current.mastery * current.attempt_count) + (1.0 if correct else 0.0)
        ) / new_attempt_count

        new_difficulty = self._adjust_difficulty(
            current.difficulty,
            new_consecutive_correct,
            new_consecutive_incorrect,
        )

        record = ProgressRecord(
            user_id=user_id,
            plugin_id=plugin_id,
            knowledge_point_id=knowledge_point_id,
            mastery=round(new_mastery, 3),
            attempt_count=new_attempt_count,
            consecutive_correct=new_consecutive_correct,
            consecutive_incorrect=new_consecutive_incorrect,
            difficulty=new_difficulty,
        )

        if matching:
            records[records.index(matching[0])] = record
        else:
            records.append(record)

        return record

    def check_dynamic_thresholds(
        self,
        user_id: str,
        plugin_id: str,
    ) -> str:
        key = f"{user_id}:{plugin_id}"
        records = self._records.get(key, [])
        if not records:
            return "maintain"

        adv_count = sum(
            1 for r in records if r.consecutive_correct >= 3 and r.mastery >= 0.9
        )
        down_count = sum(
            1 for r in records if r.consecutive_incorrect >= 3 and r.mastery < 0.6
        )
        if adv_count > 0:
            return "advance"
        if down_count > 0:
            return "downgrade"
        return "maintain"

    def _adjust_difficulty(
        self,
        current: str,
        consecutive_correct: int,
        consecutive_incorrect: int,
    ) -> str:
        levels = ["intro", "basic", "advanced", "comprehensive"]
        try:
            idx = levels.index(current)
        except ValueError:
            idx = 0

        if consecutive_correct >= 3 and idx < len(levels) - 1:
            return levels[idx + 1]
        if consecutive_incorrect >= 3 and idx > 0:
            return levels[idx - 1]
        return current
