"""Test API endpoints that don't require full orchestrator."""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.llm.client import LLMClient


def _make_mock_llm() -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.model = "deepseek-v4-pro"
    return llm


def test_training_quiz_and_submission(tmp_path):
    """Quiz/submit endpoints work independently of orchestrator."""
    app = create_app(db_path=tmp_path / "api.sqlite", llm_client=_make_mock_llm())
    client = TestClient(app)

    # 真实题库：按技能点出题
    quiz = client.post("/training/quizzes", json={
        "knowledge_point_ids": ["b01__skill_00001"], "difficulty": "",
    }).json()
    assert quiz["questions"]
    q = quiz["questions"][0]
    assert q["options"], "真实题库应为四选一客观题"
    assert q["knowledge_point_id"] == "b01__skill_00001"

    # 提交正确字母 → 判对
    submission = client.post("/training/submissions", json={
        "user_id": "u1", "question_id": q["question_id"], "answer": q["answer"],
    }).json()
    assert submission["correct"] is True

    # 边界：未知题目 → 404（而不是 500）
    resp = client.post("/training/submissions", json={
        "user_id": "u1", "question_id": "no_such_question", "answer": "A",
    })
    assert resp.status_code == 404

    # 边界：空答案 → 判错，不崩溃
    empty = client.post("/training/submissions", json={
        "user_id": "u1", "question_id": q["question_id"], "answer": "",
    }).json()
    assert empty["correct"] is False


def test_asset_api_flow(tmp_path):
    """计划/报告生成后落库为文件资产；列表/详情/删除闭环。"""
    from unittest.mock import patch

    from brain_of_cloud.domain.models import MasteryReport
    from brain_of_cloud.services.agents import LearningPlannerAgent, TrainingAnalyzerAgent

    app = create_app(db_path=tmp_path / "assets_api.sqlite", llm_client=_make_mock_llm())
    client = TestClient(app)

    # 新用户资产列表为空
    assert client.get("/users/u1/assets").json()["total"] == 0

    # 工具箱生成计划 → 落为「plan」资产
    with patch.object(LearningPlannerAgent, "run", return_value="第1周：学习《政策与法律法规》…"):
        resp = client.post("/training/plan", json={"user_id": "u1"})
    assert resp.status_code == 200
    assert resp.json()["plan"]

    # 工具箱生成报告 → 落为「report」资产
    report = MasteryReport(
        report_id="r1", user_id="u1",
        knowledge_point_scores={}, weak_points=[],
        recommended_action="建议先复习接站流程。",
    )
    with patch.object(TrainingAnalyzerAgent, "run", return_value=report):
        resp = client.post("/training/report", json={"user_id": "u1"})
    assert resp.status_code == 200

    # 列表 + 类型过滤
    rows = client.get("/users/u1/assets").json()
    assert rows["total"] == 2
    plans = client.get("/users/u1/assets", params={"asset_type": "plan"}).json()
    assert plans["total"] == 1

    # 详情
    aid = plans["assets"][0]["asset_id"]
    detail = client.get(f"/assets/{aid}").json()
    assert detail["asset_type"] == "plan"
    assert "第1周" in detail["content"]

    # 删除闭环 → 详情/二次删除 404
    assert client.delete(f"/assets/{aid}").status_code == 200
    assert client.get(f"/assets/{aid}").status_code == 404
    assert client.delete(f"/assets/{aid}").status_code == 404


def test_asset_unknown_404(tmp_path):
    """不存在的资产 → 404 而非 500。"""
    app = create_app(db_path=tmp_path / "assets_404.sqlite", llm_client=_make_mock_llm())
    client = TestClient(app)
    assert client.get("/assets/no_such_asset").status_code == 404
