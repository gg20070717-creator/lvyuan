"""Tests for the async /messages + GET /tasks/{id} flow."""

import time
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.domain.models import AgentId, Message, Task, TaskStatus
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.orchestrator import Orchestrator, OrchestratorResult


def _make_mock_llm():
    llm = MagicMock(spec=LLMClient)
    llm.model = "deepseek-v4-pro"
    return llm


def _wait_task(client, task_id, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/tasks/{task_id}").json()
        if r["status"] in ("completed", "failed"):
            return r
        time.sleep(0.2)
    raise AssertionError(f"task {task_id} not finished in {timeout}s")


def _fake_handle(self, *, user_id, session_id, content):
    time.sleep(0.2)
    return OrchestratorResult(
        task=Task(
            task_id="t", user_id=user_id, session_id=session_id,
            plugin_id="p", status=TaskStatus.COMPLETED,
        ),
        input_message=Message(
            message_id="m", task_id="t", from_agent=AgentId.CONCIERGE,
            content=content, lsn=1,
        ),
        response=f"echo:{content}",
        tool_calls_made=["search_knowledge"],
        review_verdict="passed",
        assets=[{"asset_id": "asset_abc", "title": "突发事件讲义", "asset_type": "lecture"}],
    )


def test_message_async_and_poll(tmp_path, monkeypatch):
    monkeypatch.setattr(Orchestrator, "handle_user_message", _fake_handle)
    app = create_app(db_path=tmp_path / "async.sqlite", llm_client=_make_mock_llm())
    client = TestClient(app)

    r = client.post("/messages", json={
        "user_id": "u_async", "session_id": "s_async", "content": "你好",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["task_id"].startswith("task_")
    assert data["content"] == ""

    res = _wait_task(client, data["task_id"], timeout=15)
    assert res["status"] == "completed"
    assert res["phase"] == "done"  # 阶段透出（差距项 T6）
    assert res["content"] == "echo:你好"
    assert res["review"] == "passed"
    assert "search_knowledge" in res["tool_calls"]
    # 任务结果透传资产列表（对话生成的文件资产）
    assert res["assets"] == [{"asset_id": "asset_abc", "title": "突发事件讲义", "asset_type": "lecture"}]


def test_task_failure_propagates(tmp_path, monkeypatch):
    def _fail(self, **kwargs):
        raise RuntimeError("模拟失败")

    monkeypatch.setattr(Orchestrator, "handle_user_message", _fail)
    app = create_app(db_path=tmp_path / "fail.sqlite", llm_client=_make_mock_llm())
    client = TestClient(app)
    r = client.post("/messages", json={"user_id": "u", "session_id": "s", "content": "x"})
    res = _wait_task(client, r.json()["task_id"], timeout=10)
    assert res["status"] == "failed"
    assert "模拟失败" in res["error"]


def test_task_not_found(tmp_path):
    app = create_app(db_path=Path(tmp_path) / "nf.sqlite", llm_client=_make_mock_llm())
    client = TestClient(app)
    assert client.get("/tasks/nonexistent").status_code == 404
