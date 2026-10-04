"""初试引导 / 学习路径规划（M1b）REST 接口。

- GET  /onboarding/questions   6 道身份题
- GET  /onboarding/groups      7 知识域 × 84 分组（第二层）
- GET  /onboarding/state       是否完成初试 + 画像
- POST /onboarding/submit      保存答案 → 生成 persona → 按 84 组自评写 baseline
- POST /learning-path/plan     管家排 84 组（LLM）→ 校验 → 重试 → 落库 learning_paths
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from brain_of_cloud.services.onboarding import (
    IDENTITY_QUESTIONS,
    apply_baseline,
    build_group_index,
    build_persona,
    compute_blindspots,
    compute_domain_snapshot,
    default_group_status,
    generate_insight,
    plan_route,
    plan_to_route,
    sync_learner_profile,
)


class OnboardingSubmitRequest(BaseModel):
    user_id: str
    answers: dict[str, str] = {}
    group_status: dict[str, str] = {}


class LearningPathPlanRequest(BaseModel):
    user_id: str
    feedback: str = ""


class RefreshProfileRequest(BaseModel):
    user_id: str


class InsightRequest(BaseModel):
    user_id: str


class QAAnswerRequest(BaseModel):
    user_id: str
    question_id: str
    option_id: str




def _qa_state(store, user_id: str) -> dict:
    profile = store.get_onboarding_profile(user_id)
    total = len(IDENTITY_QUESTIONS)
    if profile:
        return {"pending": False, "identity_done": True, "step": total, "total": total,
                "answers": profile.get("identity_answers") or {}, "question": None}
    qa = store.get_onboarding_qa(user_id)
    answers = qa.get("answers") or {}
    step = int(qa.get("step") or 0)
    done = step >= total
    question = None
    if not done:
        q = IDENTITY_QUESTIONS[step]
        question = {"id": q["id"], "question": q["question"], "options": q["options"]}
    return {"pending": not done, "identity_done": done, "step": step, "total": total,
            "answers": answers, "question": question}


def _qa_public(state: dict, lead: str) -> dict:
    out = dict(state)
    out["lead"] = lead
    return out

def create_onboarding_router(plugin: Any, store: Any, llm_client: Any) -> APIRouter:
    router = APIRouter(tags=["onboarding", "learning-path"])

    def _index() -> dict:
        return build_group_index(plugin)

    @router.get("/onboarding/qa/state")
    def onboarding_qa_state(user_id: str) -> dict:
        st = _qa_state(store, user_id)
        return _qa_public(st, "")

    @router.post("/onboarding/qa/answer")
    def onboarding_qa_answer(req: QAAnswerRequest) -> dict:
        st = _qa_state(store, req.user_id)
        if st.get("identity_done"):
            return _qa_public(st, "身份题已全部完成。")
        q = st.get("question")
        if not q or q["id"] != req.question_id:
            raise HTTPException(status_code=409, detail="题目状态已变化，请刷新后重试")
        if not any(o["id"] == req.option_id for o in q["options"]):
            raise HTTPException(status_code=422, detail="无效选项")
        answers = dict(st.get("answers") or {})
        answers[req.question_id] = req.option_id
        store.save_onboarding_qa(req.user_id, st["step"] + 1, answers)
        st2 = _qa_state(store, req.user_id)
        lead = "已收到，我们继续。" if not st2.get("identity_done") else "身份题已答完，请完成下方能力自评。"
        return _qa_public(st2, lead)

    @router.get("/onboarding/questions")
    def onboarding_questions() -> dict:
        return {"questions": IDENTITY_QUESTIONS}

    @router.get("/onboarding/groups")
    def onboarding_groups() -> dict:
        idx = _index()
        return {
            "domains": idx["domains"],
            "total_domains": len(idx["domains"]),
            "total_groups": len(idx["order"]),
            "order": idx["order"],
        }

    @router.get("/onboarding/state")
    def onboarding_state(user_id: str) -> dict:
        profile = store.get_onboarding_profile(user_id)
        identity_answers = (profile or {}).get("identity_answers")
        if not identity_answers:
            identity_answers = (store.get_onboarding_qa(user_id) or {}).get("answers") or {}
        return {"user_id": user_id, "done": profile is not None,
                "profile": profile, "identity_answers": identity_answers or None}

    @router.post("/onboarding/submit")
    def onboarding_submit(req: OnboardingSubmitRequest) -> dict:
        if not req.user_id:
            raise HTTPException(status_code=422, detail="user_id 不能为空")
        idx = _index()
        answers = dict(req.answers or {})
        if not answers:
            answers = (store.get_onboarding_qa(req.user_id) or {}).get("answers") or {}
        persona = build_persona(answers)
        defaults = default_group_status(persona, idx["groups"])
        merged = dict(defaults)
        for gid, st in (req.group_status or {}).items():
            if gid in idx["groups"]:
                merged[gid] = st
        counts = apply_baseline(store, req.user_id, merged, idx["groups"])
        store.save_onboarding_profile(req.user_id, persona, answers, merged)
        sync_learner_profile(store, req.user_id, persona, answers)  # 回写旧画像，打通两套数据
        return {"ok": True, "done": True, "user_id": req.user_id,
                "persona": persona, "counts": counts, "group_status": merged}

    @router.get("/learning-path/blindspots")
    def learning_path_blindspots(user_id: str) -> dict:
        idx = _index()
        snap = compute_domain_snapshot(store, plugin, user_id, idx)
        return {"domains": snap["domains"], "blindspots": snap["weak"]}

    @router.get("/onboarding/insight")
    def onboarding_insight_get(user_id: str) -> dict:
        profile = store.get_onboarding_profile(user_id)
        return {"ok": True, "user_id": user_id, "insight": (profile or {}).get("insight") or {}}

    @router.post("/onboarding/insight")
    def onboarding_insight_generate(req: InsightRequest) -> dict:
        profile = store.get_onboarding_profile(req.user_id)
        if not profile:
            raise HTTPException(status_code=409, detail="请先完成初试引导")
        persona = profile.get("persona") or {}
        idx = _index()
        bs = compute_blindspots(store, plugin, req.user_id, idx)
        insight = generate_insight(llm_client, persona, bs)
        store.save_onboarding_profile(
            req.user_id, persona,
            profile.get("identity_answers") or {},
            profile.get("group_status") or {},
            insight=insight,
        )
        return {"ok": True, "user_id": req.user_id, "insight": insight}

    @router.post("/onboarding/refresh-profile")
    def onboarding_refresh_profile(req: RefreshProfileRequest) -> dict:
        profile = store.get_onboarding_profile(req.user_id)
        if not profile:
            raise HTTPException(status_code=409, detail="请先完成初试引导")
        answers = profile.get("identity_answers") or {}
        group_status = profile.get("group_status") or {}
        persona = build_persona(answers)
        version = store.save_profile_snapshot(req.user_id, persona, source="refresh")
        # 刷新画像 = 让管家基于最新掌握度/盲区重新评价一次
        idx = _index()
        bs = compute_blindspots(store, plugin, req.user_id, idx)
        insight = generate_insight(llm_client, persona, bs)
        store.save_onboarding_profile(req.user_id, persona, answers, group_status, insight=insight)
        sync_learner_profile(store, req.user_id, persona, answers)
        return {"ok": True, "user_id": req.user_id, "version": version,
                "persona": persona, "insight": insight}

    @router.get("/onboarding/records")
    def onboarding_records(user_id: str) -> dict:
        profile = store.get_onboarding_profile(user_id)
        return {
            "user_id": user_id,
            "persona": (profile or {}).get("persona"),
            "updated_at": (profile or {}).get("updated_at"),
            "profile_snapshots": store.list_profile_snapshots(user_id),
            "learning_paths": store.list_learning_paths(user_id),
        }

    @router.get("/learning-path/latest")
    def learning_path_latest(user_id: str) -> dict:
        lp = store.get_latest_learning_path(user_id)
        if not lp:
            return {"found": False, "user_id": user_id}
        return {
            "found": True, "user_id": user_id,
            "version": int(lp["version"]),
            "status": lp.get("status") or "",
            "created_at": lp.get("created_at") or "",
            "route": lp.get("route") or {},
        }

    @router.post("/learning-path/plan")
    def learning_path_plan(req: LearningPathPlanRequest) -> dict:
        profile = store.get_onboarding_profile(req.user_id)
        if not profile:
            raise HTTPException(
                status_code=409,
                detail="请先完成初试引导（POST /onboarding/submit）后再生成学习路径",
            )
        idx = _index()
        persona = profile.get("persona") or {}
        defaults = default_group_status(persona, idx["groups"])
        plan = plan_route(llm_client, idx, persona, defaults, feedback=req.feedback or "")
        note = persona.get("summary") or ""
        if req.feedback:
            note += "（已按反馈重排）"
        route = plan_to_route(req.user_id, plan, idx, defaults, note=note)
        version = store.save_learning_path(req.user_id, route)
        # 出路线时就让管家基于画像+盲区出一版报告并存档（学情中心直接可见，无需先点更新）
        try:
            p2 = store.get_onboarding_profile(req.user_id)
            if p2:
                bs = compute_blindspots(store, plugin, req.user_id, idx)
                insight = generate_insight(llm_client, p2.get("persona") or {}, bs)
                store.save_onboarding_profile(
                    req.user_id, p2.get("persona") or {},
                    p2.get("identity_answers") or {}, p2.get("group_status") or {},
                    insight=insight,
                )
        except Exception:
            pass
        return {
            "ok": plan.get("ok", False),
            "version": version,
            "fallback": bool(plan.get("fallback", False)),
            "attempts": plan.get("attempts", 0),
            "error": plan.get("error", ""),
            "note": note,
            "route": route,
        }

    return router
