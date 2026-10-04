"""Tests for the 景区讲解 · 语音实训 module (brain_of_cloud/voice)."""

import json

import pytest
from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.llm.client import LLMResponse
from brain_of_cloud.voice.evaluate import coverage_result, evaluate_scene, point_covered
from brain_of_cloud.voice.scenes import get_scene, list_scenes


# ─────────────────────────── 场景数据 ───────────────────────────

def test_scenes_have_required_fields():
    scenes = list_scenes()
    assert len(scenes) >= 3
    for s in scenes:
        assert s["scene_id"] and s["title"] and s["points"]
        assert s["duration_sec"] > 0
        # 预留字段：新知识库 / 720云 全景热点
        assert "knowledge_point_ids" in s
        assert "knowledge" in s
        assert "panorama" in s
        assert "hotspots" in s


def test_get_scene():
    assert get_scene("bund_voice") is not None
    assert get_scene("nope") is None


# ─────────────────────────── 覆盖评分 ───────────────────────────

def test_point_covered():
    tr = "外滩被称为万国建筑博览群，对岸是陆家嘴金融区。"
    assert point_covered("外滩被称为万国建筑博览群", tr) is True
    assert point_covered("适合傍晚欣赏浦江夜景", tr) is False


def test_coverage_result():
    cov = coverage_result(
        ["讲解外滩的开埠历史背景", "讲解陆家嘴金融区天际线"],
        "先讲外滩的开埠历史背景，其他的没讲",
    )
    assert cov["covered"] == ["讲解外滩的开埠历史背景"]
    assert cov["missed"] == ["讲解陆家嘴金融区天际线"]
    assert cov["coverage_score"] == 50


# ─────────────────────────── 评价（假 LLM） ───────────────────────────

class FakeLLM:
    """模拟 LLMClient.generate —— 返回固定 JSON。"""

    def __init__(self, content: str | None = None, raise_error: bool = False):
        self._content = content
        self._raise = raise_error

    def generate(self, system, user, **kwargs):
        if self._raise:
            raise RuntimeError("LLM 服务不可用")
        return LLMResponse(content=self._content or "{}")


def test_evaluate_with_fake_llm():
    scene = get_scene("bund_voice")
    tr = "外滩是万国建筑博览群，对岸是陆家嘴金融区，海关大楼和平饭店是标志建筑。"
    content = json.dumps({
        "total_score": 88,
        "strengths": ["点出了万国建筑博览群"],
        "weaknesses": ["没讲开埠历史"],
        "suggestions": ["补充外滩开埠背景"],
        "summary": "总体不错",
    }, ensure_ascii=False)
    report = evaluate_scene(scene, tr, llm_client=FakeLLM(content))
    assert report["total_score"] == 88
    assert report["coverage"]["coverage_score"] > 0
    assert "learn" in report
    assert report["learn"]["keyword"] == "外滩"


def test_evaluate_falls_back_on_llm_error():
    scene = get_scene("bund_voice")
    report = evaluate_scene(scene, "", llm_client=FakeLLM(raise_error=True))
    assert "total_score" in report
    assert "AI 点评服务暂不可用" in report["weaknesses"][0]


def test_evaluate_knows_hotspot_context():
    """720云 热点预留：传入 hotspot_id 后，评价上下文应包含热点信息。"""
    scene = get_scene("bund_voice")
    captured = {}

    class SpyLLM:
        def generate(self, system, user, **kwargs):
            captured["user"] = user
            return LLMResponse(content="{}")

    evaluate_scene(scene, "讲了海关大楼", hotspot_id="bund_hs_customs", llm_client=SpyLLM())
    assert "海关大楼" in captured["user"]
    assert "全景热点" in captured["user"]


# ─────────────────────────── API ───────────────────────────

@pytest.fixture(scope="module")
def client():
    app = create_app(llm_client=FakeLLM(json.dumps({
        "total_score": 80, "strengths": [], "weaknesses": [], "suggestions": [],
        "summary": "ok",
    }, ensure_ascii=False)))
    return TestClient(app)


def test_api_voice_scenes(client):
    r = client.get("/voice/scenes")
    assert r.status_code == 200
    assert len(r.json()["scenes"]) >= 3


def test_api_voice_evaluate(client):
    r = client.post("/voice/evaluate", json={
        "scene_id": "bund_voice",
        "transcript": "外滩是万国建筑博览群。",
        "hotspot_id": "bund_hs_customs",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["report"]["total_score"] == 80
    assert data["scene"]["scene_id"] == "bund_voice"


def test_api_voice_evaluate_unknown_scene(client):
    r = client.post("/voice/evaluate", json={"scene_id": "nope", "transcript": "x"})
    assert r.status_code == 404
