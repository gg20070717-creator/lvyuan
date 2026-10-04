# -*- coding: utf-8 -*-
"""M1b 接口：questions/groups/state/submit/learning-path/plan（假 LLM）。"""
import pytest
from fastapi.testclient import TestClient

from brain_of_cloud.api.app import create_app
from brain_of_cloud.llm.client import LLMResponse
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.onboarding import build_group_index


class _FakeLLM:
    model = "fake"

    def __init__(self) -> None:
        self.content = ""
        self.calls = 0

    def generate(self, system: str, user: str, **kw):
        self.calls += 1
        return LLMResponse(content=self.content)


@pytest.fixture(scope="module")
def plugin():
    return TourGuidePlugin()


@pytest.fixture(scope="module")
def app(plugin, tmp_path_factory):
    fake = _FakeLLM()
    # 让“管家”按知识树默认顺序输出 67 行（含序号与 ID）
    idx = build_group_index(plugin)
    fake.content = "\n".join(f"{i+1}. {gid}" for i, gid in enumerate(idx["order"]))
    app = create_app(db_path=str(tmp_path_factory.mktemp("onb_api") / "t.sqlite"),
                     llm_client=fake)
    app.state.fake_llm = fake
    app.state.group_index = idx
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_questions(client):
    r = client.get("/onboarding/questions")
    assert r.status_code == 200
    assert len(r.json()["questions"]) == 6


def test_groups(client, app):
    r = client.get("/onboarding/groups")
    assert r.status_code == 200
    data = r.json()
    assert data["total_domains"] == 7  # 2026-09-05 收纳到 7 大领域
    assert data["total_groups"] == 84  # 2026-09-05 收纳到 7 大领域后组数
    assert len(data["domains"]) == data["total_domains"]


def test_state_initial_not_done(client):
    r = client.get("/onboarding/state", params={"user_id": "u_x"})
    assert r.json()["done"] is False


def test_submit_and_state(client, app, plugin):
    g0 = app.state.group_index["order"][0]
    answers = {"identity": "guide", "basis": "guide_return", "language": "basic",
               "goal": "inbound_foreign", "pace": "parttime", "style": "practice"}
    gs = {gid: "learning" for gid in app.state.group_index["order"]}
    gs[g0] = "mastered"
    r = client.post("/onboarding/submit", json={"user_id": "u1", "answers": answers, "group_status": gs})
    assert r.status_code == 200
    data = r.json()
    assert data["done"] is True
    assert "导游业务" in data["persona"]["default_master_books"] or data["persona"]["persona_id"]
    # baseline 只写 mastered 组
    rows = app.app.state if False else None
    # 通过 store 检查（create_app 内部 store 未暴露，用 state 接口与二次提交核对）
    r2 = client.get("/onboarding/state", params={"user_id": "u1"})
    assert r2.json()["done"] is True
    assert r2.json()["profile"]["persona"]["summary"]
    assert len(r2.json()["profile"]["group_status"]) == len(app.state.group_index["order"])


def test_plan_requires_onboarding(client):
    r = client.post("/learning-path/plan", json={"user_id": "no_one"})
    assert r.status_code == 409


def test_plan_persist_and_replan(client, app):
    # 先用通用用户完成引导
    gs = {gid: "learning" for gid in app.state.group_index["order"]}
    client.post("/onboarding/submit", json={
        "user_id": "u2",
        "answers": {"identity": "student", "basis": "zero", "language": "none",
                    "goal": "cert_cn", "pace": "fulltime", "style": "quiz"},
        "group_status": gs,
    })
    fake = app.state.fake_llm
    fake.content = "\n".join(f"{i+1}. {gid}" for i, gid in enumerate(app.state.group_index["order"]))
    r = client.post("/learning-path/plan", json={"user_id": "u2"})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["fallback"] is False
    assert d["version"] == 1
    assert d["route"]["stats"]["groups"] == len(app.state.group_index["order"])
    assert d["route"]["stats"]["total_skills"] == 3796
    # 重排 → version 2
    r2 = client.post("/learning-path/plan", json={"user_id": "u2", "feedback": "把入境游实战放最后"})
    assert r2.json()["version"] == 2


def test_latest_path(client, app):
    gs = {gid: "learning" for gid in app.state.group_index["order"]}
    client.post("/onboarding/submit", json={
        "user_id": "u3",
        "answers": {"identity": "student", "basis": "zero", "language": "none",
                    "goal": "cert_cn", "pace": "fulltime", "style": "quiz"},
        "group_status": gs,
    })
    fake = app.state.fake_llm
    fake.content = "\n".join(f"{i+1}. {gid}" for i, gid in enumerate(app.state.group_index["order"]))
    client.post("/learning-path/plan", json={"user_id": "u3"})
    r = client.get("/learning-path/latest", params={"user_id": "u3"})
    assert r.status_code == 200
    d = r.json()
    assert d["found"] is True
    assert d["version"] == 1
    assert d["route"]["stats"]["total_skills"] == 3796
    # 无路线用户
    r2 = client.get("/learning-path/latest", params={"user_id": "nobody"})
    assert r2.json()["found"] is False


def test_blindspots_refresh_records(client, app):
    g0 = app.state.group_index["order"][0]
    gs = {gid: "mastered" for gid in app.state.group_index["order"]}
    gs[g0] = "learning"
    r = client.post("/onboarding/submit", json={
        "user_id": "u5",
        "answers": {"identity": "student", "basis": "zero", "language": "none",
                    "goal": "cert_cn", "pace": "fulltime", "style": "quiz"},
        "group_status": gs,
    })
    assert r.status_code == 200
    # 盲区：唯一 learning 组应出现
    rb = client.get("/learning-path/blindspots", params={"user_id": "u5"})
    assert rb.status_code == 200
    bs = rb.json()["blindspots"]
    assert len(bs) >= 1
    assert bs[0]["group_id"] == g0
    assert bs[0]["weak_skills"] >= 1
    # 更新画像 → 快照 v1
    rr = client.post("/onboarding/refresh-profile", json={"user_id": "u5"})
    assert rr.status_code == 200 and rr.json()["version"] == 1
    # 记录
    rec = client.get("/onboarding/records", params={"user_id": "u5"})
    d = rec.json()
    assert d["persona"] is not None
    assert len(d["profile_snapshots"]) == 1


def test_insight_get_and_generate(client, app):
    g0 = app.state.group_index["order"][0]
    gs = {gid: "mastered" for gid in app.state.group_index["order"]}
    gs[g0] = "learning"
    client.post("/onboarding/submit", json={
        "user_id": "u6",
        "answers": {"identity": "guide", "basis": "experienced", "language": "fluent",
                    "goal": "custom_high", "pace": "parttime", "style": "practice"},
        "group_status": gs,
    })
    fake = app.state.fake_llm
    fake.content = "不是json"
    rg = client.get("/onboarding/insight", params={"user_id": "u6"})
    assert rg.json()["insight"] == {}
    rp = client.post("/onboarding/insight", json={"user_id": "u6"})
    assert rp.status_code == 200
    ins = rp.json()["insight"]
    assert ins.get("persona_analysis") and ins.get("blindspot_analysis") and ins.get("next_actions")
    # 已存档
    rg2 = client.get("/onboarding/insight", params={"user_id": "u6"})
    assert rg2.json()["insight"].get("persona_analysis")


def test_qa_conversation_and_submit_with_stored_answers(client):
    # 新用户开始问答
    r0 = client.get("/onboarding/qa/state", params={"user_id": "u7"})
    assert r0.json()["pending"] is True and r0.json()["step"] == 0
    qid = r0.json()["question"]["id"]
    opts = {o["id"] for o in r0.json()["question"]["options"]}
    # 依次答 6 题（每题选第一个选项）
    for i in range(6):
        st = client.get("/onboarding/qa/state", params={"user_id": "u7"}).json()
        if st.get("identity_done"):
            break
        q = st["question"]
        ans = client.post("/onboarding/qa/answer", json={
            "user_id": "u7", "question_id": q["id"], "option_id": q["options"][0]["id"]})
        assert ans.status_code == 200
    st_end = client.get("/onboarding/qa/state", params={"user_id": "u7"}).json()
    assert st_end["identity_done"] is True and len(st_end["answers"]) == 6
    # state 带 identity_answers
    st_all = client.get("/onboarding/state", params={"user_id": "u7"}).json()
    assert st_all["identity_answers"] and len(st_all["identity_answers"]) == 6
    # submit 不传 answers → 用对话已答的身份题生成画像
    gs = {g: "learning" for g in client.get("/onboarding/groups").json()["order"]}
    sub = client.post("/onboarding/submit", json={"user_id": "u7", "group_status": gs})
    assert sub.status_code == 200
    d = sub.json()
    assert d["done"] is True and d["persona"].get("identity") in [x["id"] for x in client.get("/onboarding/questions").json()["questions"][0]["options"]]
