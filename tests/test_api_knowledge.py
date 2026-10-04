"""Integration tests for the knowledge + user-state API endpoints."""

import pytest
from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.api.schemas import QuizRequest
from brain_of_cloud.llm.client import LLMClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("api") / "kb.sqlite"
    app = create_app(db_path=db)
    return TestClient(app)


def test_health(client):
    r = client.get("/")
    assert r.json()["status"] == "ok"


def test_books_endpoint(client):
    r = client.get("/knowledge/books")
    data = r.json()
    assert len(data["books"]) == 7  # 2026-09-05 新增 17 本已收纳为 7 大领域下的 part
    assert data["stats"]["skills"] == 3796


def test_tree_endpoint(client):
    r = client.get("/knowledge/tree")
    data = r.json()
    assert len(data["tree"]) == 7  # 2026-09-05 新增 17 本已收纳为 7 大领域下的 part
    book = data["tree"][0]
    assert book["title"]
    assert book["children"]


def test_guides_endpoint(client):
    r = client.get("/knowledge/guides")
    data = r.json()
    assert len(data["guides"]) >= 20
    g = data["guides"][0]
    assert g["chapter_title"]
    assert g["skill_count"] > 0


def test_skill_detail(client):
    r = client.get("/knowledge/skills/b01__skill_00001")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "“一五”计划的顺利实施"
    assert len(data["content"]) > 100
    assert data["book"] == "全国导游基础知识"
    assert data["questions"], "技能点应关联真题"


def test_skill_detail_404(client):
    r = client.get("/knowledge/skills/nonexistent_skill")
    assert r.status_code == 404


def test_search_endpoint(client):
    r = client.get("/knowledge/search", params={"q": "突发事件应急处置", "top_k": 3})
    data = r.json()
    assert data["count"] >= 1
    top = data["results"][0]
    assert top["skill_id"]
    assert top["title"]
    assert top["source"]


def test_browse_questions(client):
    r = client.get(
        "/knowledge/questions",
        params={"book": "全国导游基础知识", "difficulty": "intro", "limit": 10},
    )
    data = r.json()
    assert data["total"] > 0
    for q in data["questions"]:
        assert q["options"]
        assert q["answer"]


def test_quiz_generation_real_bank(client):
    r = client.post(
        "/training/random",
        json=QuizRequest(limit=3).model_dump(),
    )
    data = r.json()
    assert len(data["questions"]) == 3
    for q in data["questions"]:
        assert q["options"]
        assert q["answer"]


def test_submission_flow_real_bank(client):
    # 取一道题，提交正确字母
    r = client.get("/knowledge/questions", params={"limit": 1})
    q = r.json()["questions"][0]
    resp = client.post(
        "/training/submissions",
        json={
            "user_id": "u_api_1",
            "question_id": q["question_id"],
            "answer": q["answer"],
        },
    )
    data = resp.json()
    assert data["correct"] is True
    assert data["mastery_report"]["knowledge_point_scores"]
    # 提交错误字母
    wrong = {"A": "B", "B": "C", "C": "D", "D": "A"}[q["answer"]]
    resp2 = client.post(
        "/training/submissions",
        json={
            "user_id": "u_api_1",
            "question_id": q["question_id"],
            "answer": wrong,
        },
    )
    assert resp2.json()["correct"] is False


def test_user_state_endpoint(client):
    # 先建画像
    client.post(
        "/profiles",
        json={
            "user_id": "u_api_2",
            "background": "我是旅游管理专业学生，目标考导游证",
            "target_role": "导游资格证",
        },
    )
    r = client.get("/users/u_api_2/state")
    data = r.json()
    assert data["profile"]["target_role"] == "导游资格证"
    assert data["memories"], "画像应沉淀为记忆"
    assert data["stats"]["total_skills"] == 3796
    assert "weak_point_titles" in data


def test_progress_uses_real_plugin_id(client):
    r = client.get("/progress/u_api_1")
    data = r.json()
    assert r.status_code == 200
    assert "mastery_report" in data


def test_clear_session(client):
    r = client.delete("/sessions/some_session")
    assert r.json()["status"] == "ok"
