from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Callable
from uuid import uuid4

from brain_of_cloud.domain.models import MasteryReport, Question, SubmissionResult
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class _SubmissionRecord:
    user_id: str
    question_id: str
    knowledge_point_id: str
    score: float


class TrainingService:
    def __init__(
        self,
        plugin: InboundGuidePlugin | None = None,
        mastery_threshold: float = 0.7,
        store: SQLiteStore | None = None,
    ) -> None:
        self._plugin = plugin or InboundGuidePlugin()
        self._mastery_threshold = mastery_threshold
        self._store = store
        self._questions_by_id = {
            question.question_id: question for question in self._plugin.questions()
        }
        self._submissions: list[_SubmissionRecord] = []

    def generate_quiz(
        self,
        knowledge_point_ids: list[str],
        difficulty: str,
        *,
        book: str | None = None,
        chapter: str | None = None,
        limit: int | None = None,
    ) -> list[Question]:
        filterable = getattr(self._plugin, "questions_filtered", None)
        if filterable is not None:
            return filterable(
                knowledge_point_ids=knowledge_point_ids or None,
                book=book,
                chapter=chapter,
                difficulty=difficulty,
                limit=limit,
            )
        return [
            question
            for question in self._plugin.questions(knowledge_point_ids)
            if question.difficulty == difficulty
        ]

    def random_quiz(
        self,
        n: int = 5,
        *,
        knowledge_point_ids: list[str] | None = None,
        difficulty: str | None = None,
        exclude_answered: set[str] | None = None,
        book: str | None = None,
        chapter: str | None = None,
    ) -> list[Question]:
        randomizer = getattr(self._plugin, "random_questions", None)
        if randomizer is not None:
            return randomizer(
                n=n,
                knowledge_point_ids=knowledge_point_ids,
                difficulty=difficulty,
                exclude_answered=exclude_answered,
                book=book,
                chapter=chapter,
            )
        pool = self.generate_quiz(
            knowledge_point_ids or [], difficulty or "intro",
            book=book, chapter=chapter,
        )
        if exclude_answered:
            pool = [q for q in pool if q.question_id not in exclude_answered]
        import random
        return random.Random(42).sample(pool, min(n, len(pool)))

    def topic_quiz_progress(
        self,
        user_id: str,
        knowledge_point_ids: list[str],
    ) -> dict:
        """统计当前教学主题相关选择题的完成进度。

        返回 {"done": int, "total": int, "exhausted": bool}：
        - total：该主题（knowledge_point_ids）下题库中带 options 的选择题总数（去重）
        - done：用户已提交过的、且属于该主题的题数（按 question_id 去重）
        - exhausted：total > 0 且 done >= total（该主题选择题全部做完）
        """
        if not knowledge_point_ids:
            return {"done": 0, "total": 0, "exhausted": False}

        filterable = getattr(self._plugin, "questions_filtered", None)
        if filterable is not None:
            topic_questions = filterable(knowledge_point_ids=knowledge_point_ids)
        else:
            topic_questions = self._plugin.questions(knowledge_point_ids)

        topic_ids = {q.question_id for q in topic_questions if q.options}
        total = len(topic_ids)

        submitted_ids = {
            record.question_id for record in self.get_submission_history(user_id)
        }
        done = len(submitted_ids & topic_ids)

        return {
            "done": done,
            "total": total,
            "exhausted": total > 0 and done >= total,
        }

    _DIFF_TEXT_LEVEL = {"intro": 1, "basic": 2, "advanced": 3, "comprehensive": 4}

    def next_progression_question(
        self,
        knowledge_point_ids: list[str] | None = None,
        *,
        exclude_answered: set[str] | None = None,
        exclude_mastered: set[str] | None = None,
    ) -> Question | None:
        """按难度从低到高取下一道未掌握的客观题（确定性顺序，供难度曲线展示）。

        - 只取选择题池（带选项，含判断正误）；
        - 排除已出过的题（exclude_answered = 教学会话 quiz_history）
          与已答对的题（exclude_mastered = quiz_correct）；
        - 难度以 difficulty_level(1-5) 升序固定排列，同难度内按 question_id 稳定排序，
          低难度全部答对后自然轮到更高难度，不随机。
        """
        filterable = getattr(self._plugin, "questions_filtered", None)
        if filterable is None:
            return None
        try:
            pool = list(filterable(knowledge_point_ids=knowledge_point_ids or None))
        except Exception:
            pool = []
        exclude = set(exclude_answered or []) | set(exclude_mastered or [])
        if exclude:
            pool = [q for q in pool if q.question_id not in exclude]
        if not pool:
            return None

        def _level(q: Question) -> int:
            if q.difficulty_level is not None:
                return int(q.difficulty_level)
            return self._DIFF_TEXT_LEVEL.get((q.difficulty or "").strip(), 5)

        pool.sort(key=lambda q: (_level(q), q.question_id))
        return pool[0]

    def get_question(self, question_id: str) -> Question | None:
        return self._questions_by_id.get(question_id)

    def submit(
        self,
        user_id: str,
        question_id: str,
        answer: str,
    ) -> SubmissionResult:
        try:
            question = self._questions_by_id[question_id]
        except KeyError as exc:
            raise KeyError(f"Unknown question_id: {question_id}") from exc

        correct, score, feedback, misconception_tags = self._grade(question, answer)

        self._submissions.append(
            _SubmissionRecord(
                user_id=user_id,
                question_id=question_id,
                knowledge_point_id=question.knowledge_point_id,
                score=score,
            )
        )
        result = SubmissionResult(
            submission_id=f"sub_{uuid4().hex}",
            user_id=user_id,
            question_id=question_id,
            score=score,
            correct=correct,
            feedback=feedback,
            misconception_tags=misconception_tags,
        )
        if self._store is not None:
            self._store.save_submission(result)
            self._update_progress_record(user_id, question, score, correct)
            if not correct:
                self._record_wrong_answer(user_id, question, answer)
        return result

    def submit_essay(
        self,
        user_id: str,
        question_id: str,
        knowledge_point_id: str,
        difficulty: str,
        prompt: str,
        rubric: str,
        answer: str,
        grader: Callable[[str, str, str], tuple[bool, float, str]],
    ) -> SubmissionResult:
        """简答题提交（AI 原创题，不在题库中）：由后台智能体 LLM 判分，落库 + 掌握度联动。

        grader(prompt, rubric, answer) -> (correct, score 0-1, feedback 中文)
        """
        correct, score, feedback = grader(prompt, rubric, answer)
        self._submissions.append(
            _SubmissionRecord(
                user_id=user_id,
                question_id=question_id,
                knowledge_point_id=knowledge_point_id,
                score=score,
            )
        )
        result = SubmissionResult(
            submission_id=f"sub_{uuid4().hex}",
            user_id=user_id,
            question_id=question_id,
            score=score,
            correct=correct,
            feedback=feedback,
            misconception_tags=[],
        )
        if self._store is not None:
            self._store.save_submission(result)
            question = Question(
                question_id=question_id,
                knowledge_point_id=knowledge_point_id,
                difficulty=difficulty,
                prompt=prompt,
                answer_key=rubric,
            )
            self._update_progress_record(user_id, question, score, correct)
            if not correct:
                self._record_wrong_answer(user_id, question, answer)
        return result

    def _grade(self, question: Question, answer: str) -> tuple[bool, float, str, list[str]]:
        """客观题按字母判分；主观题按关键词判分。返回 (correct, score, feedback, misconception_tags)。"""
        if question.options:
            # 前端提交选项字母（A-D）；与题目答案字母比对。
            # 选项经加载器规范化后必带 A./B./C./D. 前缀，答案字母与位置一致。
            submitted = answer.strip().upper()[:1] if answer.strip() else ""
            correct = submitted == question.answer.strip().upper()
            score = 1.0 if correct else 0.0
            feedback = (
                question.explanation or ("回答正确。" if correct else "回答错误。")
            )
            tags = [] if correct else list(question.misconception_tags)
            return correct, score, feedback, tags

        correct = self._is_correct(question, answer)
        score = 1.0 if correct else 0.0
        tags = [] if correct else list(question.misconception_tags)
        return correct, score, "correct" if correct else "missing key action", tags

    def get_submission_history(self, user_id: str) -> list[SubmissionResult]:
        if self._store is not None:
            return self._store.get_submissions(user_id)
        return [
            SubmissionResult(
                submission_id=f"sub_{i}",
                user_id=user_id,
                question_id=r.question_id,
                score=r.score,
                correct=r.score == 1.0,
                feedback="correct" if r.score == 1.0 else "incorrect",
            )
            for i, r in enumerate(
                [r for r in self._submissions if r.user_id == user_id]
            )
        ]

    def topic_question_pool(self, knowledge_point_ids: list[str] | None = None) -> list:
        """某主题题库内全部题（客观+简答），用于「全做完」判定。"""
        if knowledge_point_ids is None:
            return []
        allowed = set(knowledge_point_ids)
        try:
            return [q for q in self._plugin.questions() if q.knowledge_point_id in allowed]
        except Exception:
            return []

    def next_essay_question(
        self,
        knowledge_point_ids: list[str] | None = None,
        *,
        exclude_correct: set[str] | None = None,
    ):
        """按难度升序取下一道未掌握的题库简答题（无选项），全做完返回 None。
        简答题改为走题库固定题（每技能点通常 2 道），保证“做完全部题才通关/弹卡”。"""
        if not knowledge_point_ids:
            return None
        allowed = set(knowledge_point_ids)
        exclude = set(exclude_correct or [])
        pool = [
            q for q in self._plugin.questions()
            if q.knowledge_point_id in allowed and not q.options and q.question_id not in exclude
        ]
        if not pool:
            return None

        def _lv(q) -> int:
            if q.difficulty_level is not None:
                return int(q.difficulty_level)
            return self._DIFF_TEXT_LEVEL.get((q.difficulty or "").strip(), 5)

        pool.sort(key=lambda q: (_lv(q), q.question_id))
        return pool[0]

    def topic_objective_pool(self, knowledge_point_ids: list[str] | None = None) -> list:
        """某主题下全部客观题（带选项，含判断），用于难度曲线/是否做完判定。"""
        filterable = getattr(self._plugin, "questions_filtered", None)
        if filterable is None:
            return []
        try:
            return list(filterable(knowledge_point_ids=knowledge_point_ids or None))
        except Exception:
            return []


    def correct_question_ids(self, user_id: str) -> set[str]:
        """该用户历史上答对过的题目 id 集合（跨会话），用于出题时永不再作为新题重复抽出。"""
        try:
            history = self.get_submission_history(user_id)
        except Exception:
            history = []
        return {r.question_id for r in history if r.correct}

    def _record_wrong_answer(self, user_id: str, question, user_answer: str) -> None:
        """判错后把题目 + 用户错误选项写入错题本（失败不阻断判分）。"""
        try:
            skill_title = ""
            if question.knowledge_point_id:
                sk = getattr(self._plugin, "get_skill", lambda _: None)(question.knowledge_point_id)
                skill_title = getattr(sk, "title", "") or ""
            self._store.save_wrong_answer(
                user_id=user_id,
                question_id=question.question_id,
                knowledge_point_id=question.knowledge_point_id,
                skill_title=skill_title,
                prompt=question.prompt,
                options=list(question.options or []),
                user_answer=user_answer,
                correct_answer=question.answer or question.answer_key or "",
                explanation=question.explanation or "",
                difficulty=question.difficulty,
                source=question.source,
            )
        except Exception:
            pass

    def wrong_answers(self, user_id: str, limit: int = 100) -> list[dict]:
        """错题本列表（最近做错优先）。"""
        if self._store is None:
            return []
        return self._store.list_wrong_answers(user_id, limit=limit)

    def wrong_answer_stats(self, user_id: str) -> dict:
        """错题统计（总数 + 按技能点聚合）。"""
        if self._store is None:
            return {"total": 0, "by_skill": []}
        return self._store.wrong_answer_stats(user_id)

    def delete_wrong_answer(self, user_id: str, question_id: str) -> bool:
        """移除一道错题（已掌握后清除）。"""
        if self._store is None:
            return False
        return self._store.delete_wrong_answer(user_id, question_id)

    def record_wrong_note(self, user_id: str, question_id: str, note: str) -> None:
        """沉淀「降维解释」到错题记录（供「易错题·降维解释」资源引用）。失败不阻断。"""
        if self._store is None or not note:
            return
        try:
            self._store.update_wrong_reteach_note(
                user_id, question_id, (note or "").strip()[:800]
            )
        except Exception:
            pass

    def get_mastery(self, user_id: str) -> MasteryReport:
        scores_by_point: dict[str, list[float]] = defaultdict(list)
        for record in self.get_submission_history(user_id):
            kp = self._knowledge_point(record.question_id)
            if kp:
                scores_by_point[kp].append(record.score)

        knowledge_point_scores = {
            kp_id: sum(scores) / len(scores)
            for kp_id, scores in scores_by_point.items()
        }
        weak_points = [
            kp_id
            for kp_id, score in knowledge_point_scores.items()
            if score < self._mastery_threshold
        ]
        return MasteryReport(
            report_id=f"mr_{uuid4().hex}",
            user_id=user_id,
            knowledge_point_scores=knowledge_point_scores,
            weak_points=weak_points,
            recommended_action="review_weak_points" if weak_points else "advance",
        )

    def check_dynamic_thresholds(self, user_id: str) -> dict:
        """动态反馈闭环：连续 ≥3 次正确（掌握度 ≥0.9）→ 建议进阶；
        连续 ≥3 次错误（掌握度 <0.6）→ 建议降维。读取 SQLite 持久化记录。"""
        if self._store is None:
            return {"action": "maintain", "knowledge_point_ids": []}
        plugin_id = self._plugin.manifest["plugin_id"]
        records = self._store.get_progress_records(user_id, plugin_id)

        advance = [
            r.knowledge_point_id
            for r in records
            if r.consecutive_correct >= 3 and r.mastery >= 0.9
        ]
        downgrade = [
            r.knowledge_point_id
            for r in records
            if r.consecutive_incorrect >= 3 and r.mastery < 0.6
        ]
        if advance:
            return {"action": "advance", "knowledge_point_ids": advance}
        if downgrade:
            return {"action": "downgrade", "knowledge_point_ids": downgrade}
        return {"action": "maintain", "knowledge_point_ids": []}

    def _knowledge_point(self, question_id: str) -> str:
        q = self._questions_by_id.get(question_id)
        return q.knowledge_point_id if q else question_id

    # ---- 进度记录 ----

    def _update_progress_record(
        self,
        user_id: str,
        question: Question,
        score: float,
        correct: bool,
    ) -> None:
        if self._store is None or not question.knowledge_point_id:
            return
        plugin_id = self._plugin.manifest["plugin_id"]
        records = self._store.get_progress_records(user_id, plugin_id)
        current = next(
            (r for r in records if r.knowledge_point_id == question.knowledge_point_id),
            None,
        )
        attempt_count = (current.attempt_count if current else 0) + 1
        if current is None:
            consecutive_correct = 1 if correct else 0
            consecutive_incorrect = 0 if correct else 1
            mastery = 1.0 if correct else 0.0
        else:
            consecutive_correct = (current.consecutive_correct + 1) if correct else 0
            consecutive_incorrect = (current.consecutive_incorrect + 1) if not correct else 0
            mastery = ((current.mastery * (attempt_count - 1)) + score) / attempt_count

        from brain_of_cloud.domain.models import ProgressRecord

        self._store.save_progress_records(
            [
                ProgressRecord(
                    user_id=user_id,
                    plugin_id=plugin_id,
                    knowledge_point_id=question.knowledge_point_id,
                    mastery=round(mastery, 3),
                    attempt_count=attempt_count,
                    consecutive_correct=consecutive_correct,
                    consecutive_incorrect=consecutive_incorrect,
                    difficulty=question.difficulty,
                )
            ]
        )

    # ---- 旧式主观题判分（保留给 InboundGuidePlugin） ----

    def _is_correct(self, question: Question, answer: str) -> bool:
        normalized = answer.casefold()
        if self._has_negative_action(normalized):
            return False

        keyword_groups = self._keyword_groups(question.question_id)
        if not keyword_groups:
            keyword_groups = self._fallback_keyword_groups(question.answer_key)
        if not keyword_groups:
            return False
        matched_groups = sum(
            1
            for group in keyword_groups
            if any(keyword in normalized for keyword in group)
        )
        required_matches = max(1, len(keyword_groups) - 1)
        return matched_groups >= required_matches

    def _keyword_groups(self, question_id: str) -> list[tuple[str, ...]]:
        return {
            "q_welcome_1": [
                ("welcome", "欢迎"),
                ("guide", "导游", "local guide"),
                ("driver", "司机"),
                ("itinerary", "schedule", "行程"),
                ("safety", "meeting time", "集合", "安全"),
            ],
            "q_cross_1": [
                ("respect", "尊重"),
                ("explain", "解释"),
                ("avoid", "neutral", "中性", "避免"),
                ("confirm", "check", "确认"),
                ("alternative", "替代"),
            ],
            "q_emergency_1": [
                ("comfort", "reassure", "安抚"),
                ("leader", "agency", "旅行社", "领队"),
                ("police", "embassy", "consulate", "报警", "使领馆"),
                ("record", "记录"),
                ("adjust", "调整"),
            ],
        }.get(question_id, [])

    def _has_negative_action(self, normalized_answer: str) -> bool:
        negative_phrases = (
            "do not respect",
            "don't respect",
            "not respect",
            "explain nothing",
            "do not explain",
            "don't explain",
            "avoid confirming",
            "avoid confirmation",
            "do not confirm",
            "don't confirm",
            "without confirming",
            "no alternative",
            "without alternative",
            "不尊重",
            "不解释",
            "不要解释",
            "不确认",
            "不要确认",
            "避免确认",
            "不提供替代",
        )
        return any(phrase in normalized_answer for phrase in negative_phrases)

    def _fallback_keyword_groups(self, answer_key: str) -> list[tuple[str, ...]]:
        groups: list[tuple[str, ...]] = []

        english_stopwords = {
            "should",
            "then",
            "with",
            "and",
            "the",
            "them",
            "this",
            "that",
        }
        english_words = [
            word
            for word in re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", answer_key.casefold())
            if word not in english_stopwords
        ]
        groups.extend((word,) for word in dict.fromkeys(english_words))

        chinese_text = "".join(re.findall(r"[一-鿿]+", answer_key))
        chinese_terms = [
            chinese_text[index : index + 2]
            for index in range(max(len(chinese_text) - 1, 0))
        ]
        groups.extend((term,) for term in dict.fromkeys(chinese_terms) if len(term) == 2)

        return groups








