"""TrainingService.topic_quiz_progress 单测 — mock 插件 + mock store。

覆盖 6 种场景：
1. 主题下 5 道选择题、用户答过 2 道 → {done:2, total:5, exhausted:False}
2. 全部答完 → {done:5, total:5, exhausted:True}
3. 无题目的主题（total=0）→ exhausted=False
4. knowledge_point_ids 为空 → {0,0,False}
5. 重复提交同一题只计 1 次
6. 只统计带 options 的题（主题下混有无选项题时 total 正确）
"""

from brain_of_cloud.domain.models import Question, SubmissionResult
from brain_of_cloud.services import TrainingService


def _question(question_id: str, knowledge_point_id: str, options: list[str] | None = None) -> Question:
    return Question(
        question_id=question_id,
        knowledge_point_id=knowledge_point_id,
        difficulty="basic",
        prompt=f"prompt {question_id}",
        options=options or [],
        answer="A" if options else "",
    )


def _submission(user_id: str, question_id: str) -> SubmissionResult:
    return SubmissionResult(
        submission_id=f"sub_{user_id}_{question_id}",
        user_id=user_id,
        question_id=question_id,
        score=1.0,
        correct=True,
        feedback="correct",
    )


class _MockPlugin:
    """模拟 TourGuidePlugin：同时提供 questions 与 questions_filtered。"""

    def __init__(self, questions: list[Question]) -> None:
        self._questions = questions

    def questions(self, knowledge_point_ids: list[str] | None = None) -> list[Question]:
        allowed = set(knowledge_point_ids or [])
        if not allowed:
            return list(self._questions)
        return [q for q in self._questions if q.knowledge_point_id in allowed]

    def questions_filtered(
        self, *, knowledge_point_ids: list[str] | None = None, **kwargs
    ) -> list[Question]:
        return self.questions(knowledge_point_ids)


class _MockStore:
    """模拟 SQLiteStore：只实现 get_submissions。"""

    def __init__(self, submissions: list[SubmissionResult]) -> None:
        self._submissions = submissions

    def get_submissions(self, user_id: str) -> list[SubmissionResult]:
        return [s for s in self._submissions if s.user_id == user_id]


def _build_service(questions: list[Question], submissions: list[SubmissionResult]) -> TrainingService:
    return TrainingService(
        plugin=_MockPlugin(questions),
        store=_MockStore(submissions),
    )


# ---- 场景 1：部分完成 ----

def test_partial_progress_returns_done_and_total():
    questions = [
        _question(f"q{i}", "kp_a", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"])
        for i in range(5)
    ]
    history = [_submission("user-1", "q0"), _submission("user-1", "q2")]
    service = _build_service(questions, history)

    assert service.topic_quiz_progress("user-1", ["kp_a"]) == {
        "done": 2,
        "total": 5,
        "exhausted": False,
    }


# ---- 场景 2：全部答完 ----

def test_all_done_is_exhausted():
    questions = [
        _question(f"q{i}", "kp_a", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"])
        for i in range(5)
    ]
    history = [_submission("user-1", f"q{i}") for i in range(5)]
    service = _build_service(questions, history)

    assert service.topic_quiz_progress("user-1", ["kp_a"]) == {
        "done": 5,
        "total": 5,
        "exhausted": True,
    }


# ---- 场景 3：主题下无题目 ----

def test_empty_topic_is_not_exhausted():
    questions = [
        _question("q0", "kp_a", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"]),
        _question("q1", "kp_b", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"]),
    ]
    service = _build_service(questions, [])

    assert service.topic_quiz_progress("user-1", ["kp_missing"]) == {
        "done": 0,
        "total": 0,
        "exhausted": False,
    }


# ---- 场景 4：knowledge_point_ids 为空 ----

def test_empty_knowledge_point_ids_returns_zeros():
    questions = [
        _question(f"q{i}", "kp_a", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"])
        for i in range(5)
    ]
    history = [_submission("user-1", f"q{i}") for i in range(5)]
    service = _build_service(questions, history)

    assert service.topic_quiz_progress("user-1", []) == {
        "done": 0,
        "total": 0,
        "exhausted": False,
    }


# ---- 场景 5：重复提交同一题只计 1 次 ----

def test_duplicate_submission_counts_once():
    questions = [
        _question(f"q{i}", "kp_a", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"])
        for i in range(3)
    ]
    history = [
        _submission("user-1", "q0"),
        _submission("user-1", "q0"),  # 同一题重复提交
        _submission("user-1", "q1"),
        _submission("user-1", "q_other_topic"),  # 其他主题的题不计入
    ]
    service = _build_service(questions, history)

    assert service.topic_quiz_progress("user-1", ["kp_a"]) == {
        "done": 2,
        "total": 3,
        "exhausted": False,
    }


# ---- 场景 6：只统计带 options 的题 ----

def test_only_questions_with_options_are_counted():
    choice = [
        _question(f"q{i}", "kp_a", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"])
        for i in range(4)
    ]
    essay = [
        _question("e0", "kp_a"),  # 无选项（简答/主观题）
        _question("e1", "kp_a"),
    ]
    history = [
        _submission("user-1", "q0"),
        _submission("user-1", "e0"),  # 无选项题的提交不计入 done
    ]
    service = _build_service(choice + essay, history)

    result = service.topic_quiz_progress("user-1", ["kp_a"])

    assert result["total"] == 4
    assert result["done"] == 1
    assert result["exhausted"] is False


# ---- 兜底：插件无 questions_filtered 时回退 questions() ----

def test_falls_back_to_questions_when_no_questions_filtered():
    class _LegacyPlugin(_MockPlugin):
        # 故意不定义 questions_filtered：getattr 返回 None → 回退 questions()
        pass

    questions = [
        _question(f"q{i}", "kp_a", ["A. 甲", "B. 乙", "C. 丙", "D. 丁"])
        for i in range(3)
    ]
    history = [_submission("user-1", "q0")]
    service = TrainingService(plugin=_LegacyPlugin(questions), store=_MockStore(history))

    assert service.topic_quiz_progress("user-1", ["kp_a"]) == {
        "done": 1,
        "total": 3,
        "exhausted": False,
    }
