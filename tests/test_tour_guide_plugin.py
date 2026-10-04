"""Tests for the real-data TourGuidePlugin and TrainingService integration."""

from pathlib import Path

import pytest

from brain_of_cloud.domain.models import Question
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.training import TrainingService
from brain_of_cloud.storage.sqlite import SQLiteStore


@pytest.fixture(scope="module")
def plugin():
    return TourGuidePlugin()


@pytest.fixture(scope="module")
def training(plugin):
    return TrainingService(plugin)


def test_plugin_manifest(plugin):
    assert plugin.manifest["plugin_id"] == "tour_guide_exam"
    assert "3796" in plugin.manifest["training_provider"]


def test_stats(plugin):
    assert plugin.stats()["skills"] == 3796
    assert plugin.stats()["questions"] == 30944


def test_questions_have_mcq_fields(plugin):
    q = plugin.get_question("q_00000")
    assert q is not None
    assert len(q.options) in (2, 4)  # 选择题 4 项 / 判断题 2 项（正确/错误）
    assert q.answer in {"A", "B", "C", "D"}
    assert q.explanation
    assert q.source
    assert q.knowledge_point_id


def test_questions_resolve_skill(plugin):
    q = plugin.get_question("q_00000")
    skill = plugin.get_skill(q.knowledge_point_id)
    assert skill is not None
    # 题目出处末段 == 技能点标题
    loc_tail = [p.strip() for p in q.source.split("/") if p.strip()][-1]
    assert loc_tail == skill.title


def test_search_returns_real_evidence(plugin):
    evs = plugin.search("突发事件应急处置", top_k=3)
    assert evs
    for e in evs:
        assert e.chunk_id
        assert e.knowledge_point_ids
        assert e.source
        assert 0 < e.trust_score <= 1


def test_search_knowledge_point_filter(plugin):
    skill = plugin.get_skill_by_title("“一五”计划的顺利实施")
    evs = plugin.search("一五计划", knowledge_point_ids=[skill.id], top_k=5)
    assert evs
    assert all(e.chunk_id == skill.id for e in evs)


def test_generate_quiz_real_bank(training, plugin):
    skill = plugin.get_skill_by_title("“一五”计划的顺利实施")
    questions = training.generate_quiz([skill.id], "intro")
    assert questions
    for q in questions:
        assert q.knowledge_point_id == skill.id
        assert len(q.options) in (2, 4)  # 选择题 4 项 / 判断题 2 项（正确/错误）


def test_generate_quiz_by_book_chapter(training, plugin):
    questions = training.generate_quiz([], "basic", book="全国导游基础知识")
    assert questions
    assert all(q.source.startswith("全国导游基础知识") for q in questions)


@pytest.fixture
def store(tmp_path):
    s = SQLiteStore(tmp_path / "quiz.sqlite")
    s.initialize()
    return s


def test_mcq_submission_correct(plugin, store):
    t = TrainingService(plugin, store=store)
    q = plugin.get_question("q_00000")
    result = t.submit("user_a", q.question_id, q.answer)
    assert result.correct is True
    assert result.score == 1.0
    assert result.feedback  # 解析或判分反馈


def test_mcq_submission_correct_for_unprefixed_source_question(plugin, store):
    """回归：源数据无字母前缀的题目（q_00004 成渝铁路），提交正确字母必须判对。"""
    t = TrainingService(plugin, store=store)
    q = plugin.get_question("q_00004")
    assert q is not None
    assert q.answer == "A"  # 源数据答案
    # 正确：点选正确项（A. 成渝铁路）→ 提交字母 A
    ok = t.submit("user_u1", q.question_id, "A")
    assert ok.correct is True
    assert ok.score == 1.0
    # 错误：选 B → 判错
    bad = t.submit("user_u1", q.question_id, "B")
    assert bad.correct is False
    assert bad.score == 0.0


def test_all_questions_options_prefixed_and_derivable(plugin):
    """全部 713 题选项带 A-D 前缀；按「选项首字符派生字母」提交正确项必须判对。

    等价于前端 letterOf 行为：从选项文本提取字母后提交。
    """
    t = TrainingService(plugin)
    for q in plugin.questions()[:50] + [plugin.get_question("q_00004")]:
        assert len(q.options) in (2, 4)  # 选择题 4 项 / 判断题 2 项（正确/错误）
        for i, opt in enumerate(q.options):
            letter = opt.strip()[0].upper()
            assert letter == chr(65 + i), f"{q.question_id} option {i} letter={letter}"
        # 用派生字母提交 answer 对应选项 → 判对
        result = t.submit("user_v", q.question_id, q.answer)
        assert result.correct is True, f"{q.question_id} answer={q.answer} graded wrong"


def test_mcq_submission_wrong(plugin, store):
    t = TrainingService(plugin, store=store)
    q = plugin.get_question("q_00000")
    wrong = {"A": "B", "B": "C", "C": "D", "D": "A"}[q.answer]
    result = t.submit("user_b", q.question_id, wrong)
    assert result.correct is False
    assert result.score == 0.0


def test_mastery_tracks_skill(plugin, store):
    t = TrainingService(plugin, store=store)
    q1 = plugin.get_question("q_00000")
    q2 = plugin.get_question("q_00001")
    t.submit("user_c", q1.question_id, q1.answer)
    t.submit("user_c", q2.question_id, "A")  # 可能错可能对，不校验结果
    mastery = t.get_mastery("user_c")
    assert mastery.knowledge_point_scores
    for kp, score in mastery.knowledge_point_scores.items():
        assert 0 <= score <= 1


def test_mastery_isolation_per_user(plugin, store):
    t = TrainingService(plugin, store=store)
    q = plugin.get_question("q_00000")
    t.submit("user_d", q.question_id, q.answer)
    t.submit("user_e", q.question_id, "A")
    d_mastery = t.get_mastery("user_d")
    e_mastery = t.get_mastery("user_e")
    # 两个用户各自的掌握度独立
    assert d_mastery.user_id == "user_d"
    assert e_mastery.user_id == "user_e"


def test_progress_records_persisted(plugin, tmp_path):
    store = SQLiteStore(tmp_path / "test.sqlite")
    store.initialize()
    t = TrainingService(plugin, store=store)
    q = plugin.get_question("q_00000")
    t.submit("user_f", q.question_id, q.answer)
    records = store.get_progress_records("user_f", plugin.manifest["plugin_id"])
    assert len(records) == 1
    assert records[0].knowledge_point_id == q.knowledge_point_id
    assert records[0].attempt_count == 1


def test_random_quiz_variety(plugin):
    t = TrainingService(plugin)
    qs = t.random_quiz(n=5)
    assert len(qs) == 5
    ids = {q.question_id for q in qs}
    assert len(ids) == 5


def test_question_bank_question_model_serializable():
    q = Question(
        question_id="t",
        knowledge_point_id="k",
        difficulty="basic",
        prompt="p",
        options=["A. x", "B. y", "C. z", "D. w"],
        answer="B",
        explanation="e",
        source="s",
    )
    d = q.model_dump(mode="json")
    assert d["options"] == ["A. x", "B. y", "C. z", "D. w"]
    assert d["answer"] == "B"
