"""历史会话列表与切换（用户反馈：历史对话要能看到、能切换）测试。"""
from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.storage.sqlite import SQLiteStore


def _store(tmp_path):
    store = SQLiteStore(tmp_path / "s.sqlite")
    store.initialize()
    return store


def test_list_sessions_aggregates(tmp_path):
    store = _store(tmp_path)
    # 两个会话，各若干条消息
    store.save_session_message("s1", "u1", "user", "给我讲讲园林构景手法")
    store.save_session_message("s1", "u1", "assistant", "构景手法主要有……")
    store.save_session_message("s1", "u1", "user", "明白了，出几道题")
    store.save_session_message("s2", "u1", "user", "帮我制定备考计划")
    store.save_session_message("s2", "u1", "assistant", "计划如下……")
    store.save_session_message("s_other", "u2", "user", "别人的会话")

    sessions = store.list_sessions("u1")

    assert len(sessions) == 2
    # 按最后活跃时间倒序
    assert sessions[0]["session_id"] in ("s1", "s2")
    by_id = {s["session_id"]: s for s in sessions}
    assert by_id["s1"]["title"] == "给我讲讲园林构景手法"   # 首条用户消息
    assert by_id["s1"]["message_count"] == 3
    assert by_id["s1"]["updated_at"]  # 有时间
    assert "s_other" not in by_id  # 其他用户隔离


def test_list_sessions_empty_and_limit(tmp_path):
    store = _store(tmp_path)
    assert store.list_sessions("nobody") == []

    store.save_session_message("s1", "u1", "user", "第一条")
    for i in range(5):
        store.save_session_message("s2", "u1", "user", f"会话二第{i}条")
    sessions = store.list_sessions("u1", limit=1)
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "s2"  # 更新的在前


def test_sessions_api_list_and_messages(tmp_path, monkeypatch):
    store = _store(tmp_path)
    store.save_session_message("s1", "u1", "user", "你好")
    store.save_session_message("s1", "u1", "assistant", "你好呀")
    app = create_app(db_path=str(tmp_path / "s.sqlite"))

    client = TestClient(app)
    res = client.get("/sessions", params={"user_id": "u1"})
    assert res.status_code == 200
    sessions = res.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "s1"
    assert sessions[0]["title"] == "你好"

    res2 = client.get("/sessions/s1/messages")
    assert res2.status_code == 200
    msgs = res2.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "你好"
