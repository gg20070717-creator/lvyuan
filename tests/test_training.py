import pytest

from brain_of_cloud.domain.models import Question
from brain_of_cloud.services import TrainingService
from brain_of_cloud.storage.sqlite import SQLiteStore


def test_generate_quiz_filters_by_knowledge_point_and_difficulty():
    service = TrainingService()

    quiz = service.generate_quiz(["kp_welcome"], "intro")

    assert [question.question_id for question in quiz] == ["q_welcome_1"]
    assert quiz[0].knowledge_point_id == "kp_welcome"
    assert quiz[0].difficulty == "intro"


def test_wrong_answer_includes_misconception_tags():
    service = TrainingService()

    result = service.submit(
        user_id="user-tags",
        question_id="q_cross_1",
        answer="Just tell them this is the rule and they should follow it.",
    )

    assert result.correct is False
    assert result.misconception_tags == ["stereotype", "dismissive_response"]


def test_correct_answer_has_no_misconception_tags():
    service = TrainingService()

    result = service.submit(
        user_id="user-tags-ok",
        question_id="q_cross_1",
        answer="Respect the guest, explain with neutral words, confirm their need, and offer an alternative arrangement.",
    )

    assert result.correct is True
    assert result.misconception_tags == []


def test_three_consecutive_correct_triggers_advance_suggestion(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    service = TrainingService(store=store)
    answer = (
        "Welcome to China. I am your local guide and this is our driver. "
        "Today I will explain the itinerary, meeting time, lunch plan, "
        "and safety reminders."
    )
    for _ in range(3):
        service.submit("user-adv", "q_welcome_1", answer)

    suggestion = service.check_dynamic_thresholds("user-adv")

    assert suggestion["action"] == "advance"
    assert suggestion["knowledge_point_ids"] == ["kp_welcome"]


def test_three_consecutive_wrong_triggers_downgrade_suggestion(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    service = TrainingService(store=store)
    wrong = "Just tell them this is the rule and they should follow it."
    for _ in range(3):
        service.submit("user-down", "q_cross_1", wrong)

    suggestion = service.check_dynamic_thresholds("user-down")

    assert suggestion["action"] == "downgrade"
    assert suggestion["knowledge_point_ids"] == ["kp_cross_culture"]


def test_no_threshold_hit_keeps_maintain(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.initialize()
    service = TrainingService(store=store)
    service.submit("user-mnt", "q_welcome_1", "Welcome. I am the guide. Here is the plan.")

    suggestion = service.check_dynamic_thresholds("user-mnt")

    assert suggestion["action"] == "maintain"
    assert suggestion["knowledge_point_ids"] == []


def test_wrong_cross_culture_answer_marks_knowledge_point_weak():
    service = TrainingService()

    result = service.submit(
        user_id="user-1",
        question_id="q_cross_1",
        answer="Just tell them this is the rule and they should follow it.",
    )
    report = service.get_mastery("user-1")

    assert result.correct is False
    assert result.score == 0
    assert report.knowledge_point_scores["kp_cross_culture"] == 0
    assert report.weak_points == ["kp_cross_culture"]
    assert report.recommended_action == "review_weak_points"


def test_reverse_cross_culture_answer_is_not_accepted_by_keyword_stacking():
    service = TrainingService()

    result = service.submit(
        user_id="user-reverse",
        question_id="q_cross_1",
        answer="Do not respect them, explain nothing, avoid confirming alternatives.",
    )

    assert result.correct is False
    assert result.score == 0


def test_chinese_cross_culture_answer_with_key_actions_is_correct():
    service = TrainingService()

    result = service.submit(
        user_id="user-cn",
        question_id="q_cross_1",
        answer="要尊重游客的问题，用中性语言解释本地习惯，确认真实需求，并提供替代安排。",
    )

    assert result.correct is True
    assert result.score == 1


def test_correct_welcome_answer_advances_without_weak_points():
    service = TrainingService()

    result = service.submit(
        user_id="user-2",
        question_id="q_welcome_1",
        answer=(
            "Welcome to China. I am your local guide and this is our driver. "
            "Today I will explain the itinerary, meeting time, lunch plan, "
            "and safety reminders."
        ),
    )
    report = service.get_mastery("user-2")

    assert result.correct is True
    assert result.score == 1
    assert report.knowledge_point_scores["kp_welcome"] == 1
    assert report.weak_points == []
    assert report.recommended_action == "advance"


def test_mastery_is_isolated_by_user():
    service = TrainingService()

    service.submit(
        user_id="user-a",
        question_id="q_cross_1",
        answer="Just tell them this is the rule and they should follow it.",
    )
    service.submit(
        user_id="user-b",
        question_id="q_cross_1",
        answer="Respect the guest, explain with neutral words, confirm their need, and offer an alternative arrangement.",
    )

    report_a = service.get_mastery("user-a")
    report_b = service.get_mastery("user-b")

    assert report_a.knowledge_point_scores["kp_cross_culture"] == 0
    assert report_a.weak_points == ["kp_cross_culture"]
    assert report_b.knowledge_point_scores["kp_cross_culture"] == 1
    assert report_b.weak_points == []


def test_fallback_answer_key_scoring_does_not_accept_any_nonempty_answer():
    service = TrainingService(plugin=_FallbackQuestionPlugin())

    wrong = service.submit("user-fallback", "q_custom_1", "anything at all")
    correct = service.submit(
        "user-fallback",
        "q_custom_1",
        "安抚游客，然后 record the incident and contact the agency.",
    )

    assert wrong.correct is False
    assert wrong.score == 0
    assert correct.correct is True
    assert correct.score == 1


def test_submit_unknown_question_id_raises_key_error():
    service = TrainingService()

    with pytest.raises(KeyError, match="Unknown question_id: missing-question"):
        service.submit("user-3", "missing-question", "answer")


class _FallbackQuestionPlugin:
    def questions(self, knowledge_point_ids=None):
        question = Question(
            question_id="q_custom_1",
            knowledge_point_id="kp_custom",
            difficulty="basic",
            prompt="How should the guide handle this incident?",
            answer_key="应安抚游客，contact the agency, and record the incident.",
            rubric="Key actions only.",
        )
        if knowledge_point_ids and question.knowledge_point_id not in knowledge_point_ids:
            return []
        return [question]
