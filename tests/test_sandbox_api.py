"""沙盒 API（HTTP 层）测试 — mock LLM。"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.llm.client import LLMClient


def _mock_llm() -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.model = "deepseek-chat"

    def _generate(system, user, **kwargs):
        if "评估师" in system:
            payload = {
                "total": 88,
                "dims": {"表达能力": 4, "控场能力": 4, "文化知识": 5, "服务意识": 5, "互动引导": 4},
                "strengths": ["开场有吸引力", "处理得当"],
                "weaknesses": ["互动略少"],
                "suggestions": ["多设计提问环节"],
                "skill_keywords": ["导游服务规范", "讲解技巧"],
            }
        else:
            payload = {"reply": "好的，我听您的安排，谢谢。", "mood": "满意", "advanced": True}
        return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))

    llm.generate.side_effect = _generate
    return llm


def _make_client(tmp_path):
    app = create_app(db_path=tmp_path / "sandbox_api.sqlite", llm_client=_mock_llm())
    return TestClient(app)


def test_sandbox_templates_api(tmp_path):
    client = _make_client(tmp_path)
    resp = client.get("/sandbox/templates")
    assert resp.status_code == 200
    templates = resp.json()["templates"]
    assert len(templates) >= 7
    assert {t["mode"] for t in templates} == {"scenario", "narrate", "fullflow", "communication"}

    scenario = client.get("/sandbox/templates", params={"mode": "scenario"}).json()["templates"]
    assert all(t["mode"] == "scenario" for t in scenario)


def test_sandbox_create_session_api(tmp_path):
    client = _make_client(tmp_path)
    resp = client.post("/sandbox/sessions", json={
        "user_id": "u1", "template_id": "t_guzhen_violation",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["template"]["title"] == "江南古镇 · 游客违规"
    assert data["customer"]["name"]
    assert "hidden" not in data["customer"], "隐藏诉求不应下发给前端"
    assert data["messages"], "应有游客开场白"
    assert data["stage"]["index"] == 0

    # 未知模板 → 400
    bad = client.post("/sandbox/sessions", json={"user_id": "u1", "template_id": "nope"})
    assert bad.status_code == 400


def test_sandbox_send_and_get_message_api(tmp_path):
    client = _make_client(tmp_path)
    sid = client.post("/sandbox/sessions", json={
        "user_id": "u1", "template_id": "t_guzhen_violation",
    }).json()["session_id"]

    resp = client.post(f"/sandbox/sessions/{sid}/messages", json={
        "user_id": "u1", "content": "先生您好，这里是文物保护区域，请您先移步护栏外。",
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["reply"] == "好的，我听您的安排，谢谢。"
    assert result["stage_advanced"] is True

    # 会话已持久化 → 重新 GET 可恢复
    restored = client.get(f"/sandbox/sessions/{sid}").json()
    assert len(restored["messages"]) == 3  # 开场 + 导游 + 游客


def test_sandbox_end_session_api(tmp_path):
    client = _make_client(tmp_path)
    sid = client.post("/sandbox/sessions", json={
        "user_id": "u1", "template_id": "t_guzhen_violation",
    }).json()["session_id"]
    client.post(f"/sandbox/sessions/{sid}/messages", json={
        "user_id": "u1", "content": "请您先移步护栏外。",
    })

    ended = client.post(f"/sandbox/sessions/{sid}/end", json={"user_id": "u1"}).json()
    assert ended["status"] == "ended"
    assert ended["score"] == 88
    assert ended["dims"]["文化知识"] == 5
    assert ended["feedback"]["suggestions"]
    assert ended["feedback"]["recommended_skills"], "应关联知识库技能点"

    # 评估报告落为学习中心资产
    assets = client.get("/users/u1/assets").json()["assets"]
    assert any(a["asset_type"] == "report" and "沙盒评估" in a["title"] for a in assets)

    # 幂等：重复结束返回既有结果
    again = client.post(f"/sandbox/sessions/{sid}/end", json={"user_id": "u1"}).json()
    assert again["score"] == ended["score"]


def test_sandbox_user_records_api(tmp_path):
    client = _make_client(tmp_path)
    for template_id in ("t_guzhen_violation", "t_restaurant_etiquette"):
        sid = client.post("/sandbox/sessions", json={"user_id": "u1", "template_id": template_id}).json()["session_id"]
        client.post(f"/sandbox/sessions/{sid}/messages", json={"user_id": "u1", "content": "您好。"})
        client.post(f"/sandbox/sessions/{sid}/end", json={"user_id": "u1"})

    records = client.get("/sandbox/users/u1/records").json()["records"]
    assert len(records) == 2
    assert all(r["score"] is not None for r in records)
    titles = {r["title"] for r in records}
    assert "江南古镇 · 游客违规" in titles


def test_sandbox_api_unknown_session_404(tmp_path):
    client = _make_client(tmp_path)
    assert client.get("/sandbox/sessions/nope").status_code == 404
    assert client.post("/sandbox/sessions/nope/messages", json={"user_id": "u1", "content": "hi"}).status_code == 404
    assert client.post("/sandbox/sessions/nope/end", json={"user_id": "u1"}).status_code == 404


def test_sandbox_send_to_ended_session_404(tmp_path):
    client = _make_client(tmp_path)
    sid = client.post("/sandbox/sessions", json={
        "user_id": "u1", "template_id": "t_guzhen_violation",
    }).json()["session_id"]
    client.post(f"/sandbox/sessions/{sid}/messages", json={"user_id": "u1", "content": "您好。"})
    client.post(f"/sandbox/sessions/{sid}/end", json={"user_id": "u1"})
    resp = client.post(f"/sandbox/sessions/{sid}/messages", json={"user_id": "u1", "content": "还能继续吗？"})
    assert resp.status_code == 404
