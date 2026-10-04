from brain_of_cloud.domain.models import AgentId, Mention, RunStatus, TaskStatus
from brain_of_cloud.domain.models import (
    LearnerProfile,
    ProgressRecord,
    SubmissionResult,
)
from brain_of_cloud.storage.sqlite import SQLiteStore
import pytest


def test_store_creates_task_and_message_with_structured_mentions(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()

    task = store.create_task(
        user_id="user_1",
        session_id="session_1",
        plugin_id="inbound_tour_local_guide",
    )
    message = store.create_message(
        task_id=task.task_id,
        from_agent=AgentId.CONCIERGE,
        content="Create a welcome script.",
        mentions=[
            Mention(
                agent_id=AgentId.TEXT_GENERATOR,
                reason="generate_learning_resource",
                payload={"resource_type": "lecture"},
            )
        ],
    )

    loaded = store.get_message(message.message_id)
    assert loaded.task_id == task.task_id
    assert loaded.mentions[0].agent_id == AgentId.TEXT_GENERATOR
    assert loaded.mentions[0].payload["resource_type"] == "lecture"


def test_store_creates_agent_run_once_per_agent_task_message(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    task = store.create_task("user_1", "session_1", "inbound_tour_local_guide")
    message = store.create_message(
        task.task_id,
        AgentId.CONCIERGE,
        "Analyze training result.",
        [Mention(agent_id=AgentId.TRAINING_ANALYZER, reason="analyze_training")],
    )

    first = store.enqueue_agent_run(
        task.task_id,
        message.message_id,
        AgentId.TRAINING_ANALYZER,
    )
    second = store.enqueue_agent_run(
        task.task_id,
        message.message_id,
        AgentId.TRAINING_ANALYZER,
    )

    assert first.run_id == second.run_id
    assert first.status.value == "pending"
    assert first.input_message_ids == [message.message_id]
    assert store.get_task(task.task_id).status == TaskStatus.CREATED


def test_first_message_lsn_starts_at_one_even_after_task_creation(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    task = store.create_task("user_1", "session_1", "inbound_tour_local_guide")

    message = store.create_message(
        task.task_id,
        AgentId.CONCIERGE,
        "Start session.",
    )

    assert message.lsn == 1


def test_agent_run_rejects_message_from_different_task(tmp_path):
    store = SQLiteStore(tmp_path / "nested" / "mvp.sqlite")
    store.initialize()
    first_task = store.create_task("user_1", "session_1", "inbound_tour_local_guide")
    second_task = store.create_task("user_1", "session_1", "inbound_tour_local_guide")
    first_message = store.create_message(
        first_task.task_id,
        AgentId.CONCIERGE,
        "Start first task.",
    )

    with pytest.raises(ValueError, match="does not belong"):
        store.enqueue_agent_run(
            second_task.task_id,
            first_message.message_id,
            AgentId.TEXT_GENERATOR,
        )


def test_agent_run_recovers_when_unique_insert_race_already_created_run(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    task = store.create_task("user_1", "session_1", "inbound_tour_local_guide")
    message = store.create_message(
        task.task_id,
        AgentId.CONCIERGE,
        "Generate a welcome script.",
    )
    with store._connect() as conn:
        conn.execute(
            """
            CREATE TRIGGER inject_agent_run_race
            BEFORE INSERT ON agent_runs
            WHEN NEW.run_id != 'run_from_race'
            BEGIN
                INSERT INTO agent_runs VALUES (
                    'run_from_race',
                    NEW.task_id,
                    NEW.message_id,
                    NEW.agent_id,
                    'pending',
                    NEW.input_message_ids_json,
                    NULL,
                    0,
                    NULL
                );
            END;
            """
        )

    run = store.enqueue_agent_run(
        task.task_id,
        message.message_id,
        AgentId.TEXT_GENERATOR,
    )

    assert run.run_id == "run_from_race"
    assert run.input_message_ids == [message.message_id]


def test_store_updates_task_status_and_completes_agent_run(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    task = store.create_task("user_1", "session_1", "inbound_tour_local_guide")
    input_message = store.create_message(
        task.task_id,
        AgentId.CONCIERGE,
        "Generate a welcome script.",
    )
    output_message = store.create_message(
        task.task_id,
        AgentId.TEXT_GENERATOR,
        "Welcome script.",
    )
    run = store.enqueue_agent_run(
        task.task_id,
        input_message.message_id,
        AgentId.TEXT_GENERATOR,
    )

    updated_task = store.update_task_status(task.task_id, TaskStatus.COMPLETED)
    completed_run = store.complete_agent_run(run.run_id, output_message.message_id)
    runs = store.list_agent_runs(task.task_id)

    assert updated_task.status == TaskStatus.COMPLETED
    assert store.get_task(task.task_id).status == TaskStatus.COMPLETED
    assert completed_run.status == RunStatus.COMPLETED
    assert completed_run.output_message_id == output_message.message_id
    assert runs == [completed_run]


def test_save_and_get_submission(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    sub = SubmissionResult(
        submission_id="sub_test",
        user_id="user_1",
        question_id="q_welcome_1",
        score=1.0,
        correct=True,
        feedback="correct",
    )
    store.save_submission(sub)
    submissions = store.get_submissions("user_1")
    assert len(submissions) == 1
    assert submissions[0].submission_id == "sub_test"
    assert submissions[0].correct is True


def test_save_and_get_learner_profile(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    profile = LearnerProfile(
        user_id="user_1",
        background="旅游管理专业学生",
        target_role="入境游地陪导游",
        current_level="intro",
        style_preferences={"mode": "实操优先"},
        baseline_scores={"kp_welcome": 0.5},
    )
    store.save_learner_profile(profile)
    loaded = store.get_learner_profile("user_1")
    assert loaded is not None
    assert loaded.user_id == "user_1"
    assert loaded.style_preferences["mode"] == "实操优先"


def test_get_nonexistent_learner_profile_returns_none(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    assert store.get_learner_profile("nonexistent") is None


def test_save_and_get_progress_records(tmp_path):
    store = SQLiteStore(tmp_path / "mvp.sqlite")
    store.initialize()
    records = [
        ProgressRecord(
            user_id="user_1",
            plugin_id="inbound_tour",
            knowledge_point_id="kp_welcome",
            mastery=0.75,
            attempt_count=3,
            consecutive_correct=2,
            difficulty="basic",
        ),
        ProgressRecord(
            user_id="user_1",
            plugin_id="inbound_tour",
            knowledge_point_id="kp_pickup",
            mastery=0.4,
            attempt_count=1,
            consecutive_incorrect=1,
            difficulty="intro",
        ),
    ]
    store.save_progress_records(records)
    loaded = store.get_progress_records("user_1", "inbound_tour")
    assert len(loaded) == 2
    assert loaded[0].knowledge_point_id == "kp_pickup"  # sorted by kp_id
    assert loaded[1].mastery == 0.75
