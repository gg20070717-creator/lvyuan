"""数据合规：导出 / 删除用户数据测试（差距项 T7）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from brain_of_cloud.domain.models import Asset, AssetType
from brain_of_cloud.storage.sqlite import SQLiteStore
from brain_of_cloud.services.assets import AssetService


def _store(tmp_path):
    store = SQLiteStore(tmp_path / "test_compliance.sqlite")
    store.initialize()
    return store


def _seed_user(store: SQLiteStore, user_id: str = "u1") -> None:
    store.save_learner_profile(
        store._learner_profile_from_dict(
            {
                "user_id": user_id,
                "background": "旅游管理专业学生",
                "target_role": "导游资格证",
                "current_level": "intro",
            }
        )
        if hasattr(store, "_learner_profile_from_dict")
        else _profile(user_id)
    )
    store.save_memory("mem_1", user_id, "goal", "目标：通过导游证考试", 0.9, "s1")
    store.save_asset(
        Asset(
            asset_id="a1",
            user_id=user_id,
            session_id="s1",
            title="讲义",
            asset_type=AssetType.LECTURE,
            content="内容",
            source_tool="generate_material",
        )
    )
    store.save_session_message("s1", user_id, "user", "你好")
    store.save_session_message("s1", user_id, "assistant", "你好，我是司南")


def _profile(user_id: str):
    from brain_of_cloud.domain.models import LearnerProfile
    return LearnerProfile(
        user_id=user_id,
        background="旅游管理专业学生",
        target_role="导游资格证",
        current_level="intro",
    )


def test_export_packages_all_user_data(tmp_path):
    store = _store(tmp_path)
    _seed_user(store)

    data = store.export_user_data("u1", "inbound_tour_local_guide")

    assert data["user_id"] == "u1"
    assert data["profile"] is not None
    assert data["profile"]["background"] == "旅游管理专业学生"
    assert len(data["memories"]) == 1
    assert data["memories"][0]["content"] == "目标：通过导游证考试"
    assert len(data["assets"]) == 1
    assert data["assets"][0]["asset_id"] == "a1"
    assert len(data["session_messages"]) == 2
    assert "exported_at" in data


def test_delete_user_data_removes_all(tmp_path):
    store = _store(tmp_path)
    _seed_user(store)
    store.save_asset(
        Asset(
            asset_id="keep",
            user_id="other",
            session_id="s9",
            title="别人的资产",
            asset_type=AssetType.TEXT,
            content="x",
            source_tool="generate_material",
        )
    )

    store.delete_user_data("u1", "inbound_tour_local_guide")

    assert store.get_learner_profile("u1") is None
    assert store.get_memories("u1") == []
    assert store.get_assets("u1") == []
    assert store.get_submissions("u1") == []
    # 其他用户数据不受影响
    assert store.get_assets("other")[0]["asset_id"] == "keep"


def test_delete_user_data_with_tasks_and_messages(tmp_path):
    """有对话任务（tasks/messages/agent_runs 外键）时删除不报错（回归：500 修复）。"""
    from brain_of_cloud.domain.models import AgentId
    store = _store(tmp_path)
    _seed_user(store)
    task = store.create_task("u1", "s1", "inbound_tour_local_guide")
    msg = store.create_message(
        task.task_id, AgentId.CONCIERGE, "你好",
        mentions=[],
    )
    store.enqueue_agent_run(task.task_id, msg.message_id, AgentId.RETRIEVAL)
    store.complete_agent_run(store.list_agent_runs(task.task_id)[0].run_id)

    store.delete_user_data("u1", "inbound_tour_local_guide")

    assert store.get_learner_profile("u1") is None
    assert store.get_memories("u1") == []


def test_export_api_roundtrip(tmp_path):
    from brain_of_cloud.api.app import create_app
    app = create_app(db_path=tmp_path / "api.sqlite")
    client = TestClient(app)
    client.post("/profiles", json={"user_id": "u-api", "background": "英语专业"})
    client.post(
        "/training/submissions",
        json={"user_id": "u-api", "question_id": "q_welcome_1", "answer": "Welcome! I am the guide."},
    )

    resp = client.get("/users/u-api/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "u-api"
    assert data["profile"]["background"] == "英语专业"

    # 提交判分响应携带 adjustment 与错因标签（差距项 T1/T2）
    quiz = client.post(
        "/training/random",
        json={"knowledge_point_ids": [], "difficulty": "intro", "limit": 1},
    ).json()
    qid = quiz["questions"][0]["question_id"]
    sub = client.post(
        "/training/submissions",
        json={"user_id": "u-api", "question_id": qid, "answer": "Z"},
    ).json()
    assert sub["adjustment"]["action"] in ("advance", "downgrade", "maintain")
    assert isinstance(sub["submission"]["misconception_tags"], list)

    # 删除后导出应为空
    deleted = client.delete("/users/u-api/data")
    assert deleted.status_code == 200
    after = client.get("/users/u-api/export").json()
    assert after["profile"] is None
    assert after["assets"] == []
