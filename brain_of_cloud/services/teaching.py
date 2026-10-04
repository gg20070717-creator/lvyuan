"""TeachingStateService — 一对一教学会话状态机。

六步教学循环：定目标(goal_setting) → 讲解(teaching) → 查理解(checking)
→ 练习(practicing) → 纠错(feedback) → 小结(closing)。

状态持久化于 SQLite（teaching_sessions 表）。阶段迁移由本服务在代码层强制执行
（出题硬校验、判分后强制反馈），不依赖 LLM 自觉——提示词只是软约束。
"""

from __future__ import annotations

from typing import Any

from brain_of_cloud.storage.sqlite import SQLiteStore

DIFFICULTY_ORDER = ["intro", "basic", "advanced", "comprehensive"]

VALID_STAGES = {
    "goal_setting",
    "teaching",
    "checking",
    "practicing",
    "feedback",
    "closing",
    "idle",
}


class TeachingStateService:
    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    # ── 读写 ──

    def get_or_create(self, session_id: str, user_id: str) -> dict[str, Any]:
        state = self._store.get_teaching_state(session_id)
        if state is None:
            state = {
                "session_id": session_id,
                "user_id": user_id,
                "topic_ids": [],
                "stage": "goal_setting",
                "depth": "intro",
                "consecutive_correct": 0,
                "consecutive_incorrect": 0,
                "quiz_history": [],
                "quiz_correct": [],
                "last_quiz": None,
                "reteach_question_id": None,
                "reteach_question": None,
                "last_outcome": None,
                "topic_finished": False,
            }
            self.save(state)
        return state

    def save(self, state: dict[str, Any]) -> None:
        self._store.save_teaching_state(
            state["session_id"], state["user_id"], state
        )

    # ── 状态迁移 ──

    def set_topic(
        self,
        session_id: str,
        user_id: str,
        topic_ids: list[str],
        depth: str | None = None,
    ) -> dict[str, Any]:
        """锁定教学主题 → 进入讲解阶段（重讲时覆盖原主题，计数器归零）。"""
        state = self.get_or_create(session_id, user_id)
        state["topic_ids"] = list(topic_ids)
        state["stage"] = "teaching"
        state["depth"] = depth or "intro"
        state["consecutive_correct"] = 0
        state["consecutive_incorrect"] = 0
        state["quiz_history"] = []
        state["last_quiz"] = None
        state["reteach_question_id"] = None
        state["reteach_question"] = None
        state["last_outcome"] = None
        state["topic_finished"] = False
        self.save(state)
        return state

    def transit(
        self,
        session_id: str,
        user_id: str,
        stage: str,
    ) -> dict[str, Any]:
        if stage not in VALID_STAGES:
            raise ValueError(f"invalid teaching stage: {stage}")
        state = self.get_or_create(session_id, user_id)
        state["stage"] = stage
        self.save(state)
        return state

    def record_quiz(
        self,
        session_id: str,
        user_id: str,
        question_id: str,
        question_info: dict[str, Any] | None = None,
        difficulty: str | None = None,
    ) -> dict[str, Any]:
        """出题后调用：记录题目（避免重复）、缓存题目信息、进入练习阶段。"""
        state = self.get_or_create(session_id, user_id)
        history = list(state.get("quiz_history") or [])
        if question_id not in history:
            history.append(question_id)
            state["quiz_history"] = history[-30:]  # 只保留最近 30 题
        state["last_quiz"] = question_info or {
            "question_id": question_id,
        }
        if difficulty:
            state["depth"] = difficulty
        state["stage"] = "practicing"
        self.save(state)
        return state

    def record_answer(
        self,
        session_id: str,
        user_id: str,
        question_id: str,
        correct: bool,
    ) -> dict[str, Any]:
        """判分后调用：更新连续对错计数（满 3 归零）、进入反馈阶段。

        返回 next_action：
        - "reteach"  答错 → 管家必须讲错因并重讲
        - "advance"  答对且连续 ≥3 → 提示进阶（下次出题自动升难度）
        - "extend"   答对 → 补充延伸点
        """
        state = self.get_or_create(session_id, user_id)
        state["last_outcome"] = "correct" if correct else "wrong"
        if correct:
            # 记录已答对的题（供「重复答对时跳过本题、直接换新题」判定）
            correct_ids = list(state.get("quiz_correct") or [])
            if question_id not in correct_ids:
                correct_ids.append(question_id)
                state["quiz_correct"] = correct_ids[-50:]
            state["consecutive_correct"] = int(state.get("consecutive_correct") or 0) + 1
            state["consecutive_incorrect"] = 0
            if state["consecutive_correct"] >= 3:
                state["depth"] = self._bump(state["depth"], up=True)
                state["consecutive_correct"] = 0
        else:
            state["consecutive_incorrect"] = int(state.get("consecutive_incorrect") or 0) + 1
            state["consecutive_correct"] = 0
            if state["consecutive_incorrect"] >= 3:
                state["depth"] = self._bump(state["depth"], up=False)
                state["consecutive_incorrect"] = 0
        state["stage"] = "feedback"
        self.save(state)
        return state

    # ── 纠错重问闭环（硬状态机）：答错 → 同一题卡片重问 → 直到答对才解除 ──

    def begin_reteach(
        self,
        session_id: str,
        user_id: str,
        question_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """答错后进入纠错重问闭环：记录被重问的题（前端以答题卡片原样重问），
        直到学员答对它才解除。"""
        state = self.get_or_create(session_id, user_id)
        if question_info:
            state["reteach_question_id"] = str(question_info.get("question_id") or "")
            state["reteach_question"] = question_info
            # 关键：让“重问题卡”在退出/重进后依然可见可答，避免永久卡死
            state["last_quiz"] = question_info
            state["stage"] = "practicing"
        else:
            state["reteach_question_id"] = None
            state["reteach_question"] = None
        self.save(state)
        return state

    def finish_reteach(
        self,
        session_id: str,
        user_id: str,
        question_id: str | None = None,
    ) -> bool:
        """解除纠错重问标记：返回 True 表示解除的正是该题（答对收口，可进入下一题）。
        若标记指向别的题（陈旧纠错态），也会一并清除，避免卡住进度。"""
        state = self.get_or_create(session_id, user_id)
        rid = state.get("reteach_question_id")
        matched = bool(rid) and (question_id is None or str(rid) == str(question_id))
        if rid:
            state["reteach_question_id"] = None
            state["reteach_question"] = None
            self.save(state)
        return matched

    # ── 出题决策 ──

    def decide_difficulty(self, state: dict[str, Any], mastery_score: float | None) -> str:
        """难度自适应：
        - 从未练过（mastery_score=None）→ 维持当前档位
        - 掌握度 ≥0.8 → 升一档（上限 comprehensive）
        - 掌握度 <0.6 → 降一档（下限 intro）
        - 其余 → 维持当前档位
        """
        if mastery_score is None:
            return state.get("depth") or "intro"
        depth = state.get("depth") or "intro"
        idx = DIFFICULTY_ORDER.index(depth) if depth in DIFFICULTY_ORDER else 0
        if mastery_score >= 0.8:
            idx = min(idx + 1, len(DIFFICULTY_ORDER) - 1)
        elif mastery_score < 0.6:
            idx = max(idx - 1, 0)
        return DIFFICULTY_ORDER[idx]

    @staticmethod
    def _bump(depth: str, *, up: bool) -> str:
        if depth not in DIFFICULTY_ORDER:
            return "intro"
        idx = DIFFICULTY_ORDER.index(depth)
        if up:
            return DIFFICULTY_ORDER[min(idx + 1, len(DIFFICULTY_ORDER) - 1)]
        return DIFFICULTY_ORDER[max(idx - 1, 0)]




