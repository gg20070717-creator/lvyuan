from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from brain_of_cloud.api.schemas import (
    AssetDetailResponse,
    AssetListResponse,
    MessageRequest,
    MessageResponse,
    ProfileCreateRequest,
    ProfileResponse,
    ProgressResponse,
    QuestionBrowseResponse,
    QuizRequest,
    QuizResponse,
    SandboxEndRequest,
    SandboxMessageResult,
    SandboxSendMessageRequest,
    SandboxSessionCreateRequest,
    SandboxSessionResponse,
    SandboxVoiceMessagesRequest,
    SearchResponse,
    SkillDetail,
    SubmissionRequest,
    SubmissionResponse,
    TaskResponse,
    TeachingStateResponse,
    MasteryAssessRequest,
    TrainingReportRequest,
    TrainingReportResponse,
    UserStateResponse,
)
from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents import ProfileAgent, TrainingAnalyzerAgent
from brain_of_cloud.services.assets import AssetService
from brain_of_cloud.services.memory import UserMemoryService
from brain_of_cloud.services.mastery import MasteryService
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.services.sandbox import SandboxError, SandboxService
from brain_of_cloud.services.task_runner import TaskRunner
from brain_of_cloud.services.agent_catalog import AGENTS, RESERVED
from brain_of_cloud.services.training import TrainingService
from brain_of_cloud.storage.sqlite import SQLiteStore
from brain_of_cloud.voice import evaluate_scene, get_scene, list_scenes, transcribe_audio



def _load_local_env() -> None:
    """启动兜底：未设置 DEEPSEEK_API_KEY 等环境变量时，从项目根目录 local.env 读取。
    方便手动 `uv run uvicorn ...` 启动（start-dev.bat 已自带加载逻辑）。"""
    candidates = [
        Path(__file__).resolve().parents[2] / "local.env",
        Path("local.env"),
    ]
    for env_path in candidates:
        try:
            if not env_path.is_file():
                continue
        except Exception:
            continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value
        except Exception:
            pass
        break


_load_local_env()
def create_app(
    db_path: str | Path | None = None,
    llm_client: LLMClient | None = None,
    use_real_knowledge: bool = True,
) -> FastAPI:
    if llm_client is None:
        llm_client = LLMClient()

    app = FastAPI(title="Brain of Cloud · 司南礼客")
    print("[BOOT] BrainOfCloud startup OK (quiz-ctrl build 20260902-5)", flush=True)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def health():
        return {"status": "ok", "service": "BrainOfCloud"}

    # ── 领域插件：默认使用真实知识库（3796 技能点 / 30944 题）──
    if use_real_knowledge:
        from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
        plugin = TourGuidePlugin()
    else:
        plugin = InboundGuidePlugin()

    if db_path is None:
        db_path = os.environ.get("BOC_DB_PATH") or "brain_of_cloud.sqlite"
    store = SQLiteStore(db_path)
    store.initialize()
    orchestrator = Orchestrator(store=store, plugin=plugin, llm_client=llm_client)
    training = TrainingService(plugin, store=store)
    memory = UserMemoryService(store)
    assets_svc = AssetService(store)
    sandbox = SandboxService(llm_client=llm_client, store=store, plugin=plugin)
    tasks = TaskRunner()

    profile_agent = ProfileAgent(llm_client)
    training_analyzer = TrainingAnalyzerAgent(llm_client, training)

    @app.get("/agents/catalog")
    def agent_catalog():
        return {"agents": AGENTS, "reserved": RESERVED, "active_count": len(AGENTS),
                "note": "13 个学习协作角色与 4 个实战角色；3 个生成角色仍为预留。"}

    @app.get("/learning/status")
    def learning_status(user_id: str, session_id: str):
        """读取持久化学习证据，由确定性规则推荐下一步，不额外调用模型。"""
        state = store.get_teaching_state(session_id) or {}
        if state and state.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="会话属于其它账户")
        teaching = orchestrator._teaching_public(state) if state else None
        topic_ids = state.get("topic_ids") or []
        ms = MasteryService(plugin, store)
        mastery = [ms.skill_mastery(user_id, nid) for nid in topic_ids]
        score = round(sum(float(x["mastery"]) for x in mastery) / len(mastery), 1) if mastery else None
        stage = state.get("stage", "idle")
        if state.get("reteach_question_id") or state.get("consecutive_incorrect", 0) > 0:
            recommendation = {"label": "先复习错因，再作答", "reason": "当前存在待巩固的错题，继续当前题目可完成纠错闭环。", "path": "/app/home"}
        elif state.get("topic_finished") or (teaching and teaching.get("topic_done")) or (score is not None and score >= 80):
            recommendation = {"label": "进入综合实战", "reason": f"当前主题综合掌握度 {score}%" if score is not None else "当前主题题目已完成，可以在场景中检验应用能力。", "path": "/app/training?focus=integrated"}
        elif stage == "practicing":
            recommendation = {"label": "继续抽题测验", "reason": "题目已就绪，作答后会更新掌握度与难度。", "path": "/app/home"}
        else:
            recommendation = {"label": "学习后做题巩固", "reason": "先理解知识，再用题目验证，旅鸢将按作答情况调整难度。", "path": "/app/home"}
        records = sandbox.list_user_records(user_id)
        return {"teaching": teaching, "mastery": score, "profile_done": bool(store.get_onboarding_profile(user_id)),
                "quiz_count": len(state.get("quiz_history") or []), "questions_answered": len(store.get_submissions(user_id)),
                "practice_count": sum(r.get("score") is not None for r in records),
                "specialty_count": sum(r.get("score") is not None and r.get("mode") in ("scenario", "communication", "narrate") for r in records),
                "integrated_count": sum(r.get("score") is not None and r.get("mode") == "fullflow" for r in records),
                "recommendation": recommendation, "source": "teaching_state + mastery + sandbox_records"}

    # ================= 对话（异步任务） =================

    @app.post("/messages", response_model=MessageResponse)
    def post_message(request: MessageRequest) -> MessageResponse:
        """入队对话任务，立即返回 task_id；前端轮询 GET /tasks/{task_id}。

        长路径（生成讲义 + 六帽审查）需多轮 LLM 调用，耗时可达数分钟，
        因此改为异步执行，避免 HTTP 连接长时间占用。
        """

        def _builder(outcome) -> dict:
            return {
                "content": outcome.response,
                "review": outcome.review_verdict,
                "tool_calls": list(outcome.tool_calls_made),
                "assets": [dict(a) for a in outcome.assets],
                "teaching": outcome.teaching,
            }

        # ── 硬挂钩（知识技能树「去首页学习」）：只收窄检索范围到该技能点+对应题库，
        #    不改动编排器逻辑（沿用旧后端 teaching 主题机制，检索/出题自动收窄到主题技能点）。
        if request.knowledge_point_id:
            locked = plugin.get_skill(request.knowledge_point_id)
            if locked is not None:
                try:
                    orchestrator._teaching.set_topic(
                        request.session_id, request.user_id, [locked.id],
                    )
                except Exception:
                    pass

        task_id = tasks.submit(
            orchestrator.handle_user_message,
            result_builder=_builder,
            user_id=request.user_id,
            session_id=request.session_id,
            content=request.content,
            phase_cb=None,  # TaskRunner 注入绑定 task_id 的上报回调
            trace_cb=None,  # TaskRunner 注入绑定 task_id 的实时轨迹回调
        )
        return MessageResponse(task_id=task_id, status="pending", content="", review="")

    @app.get("/tasks/{task_id}", response_model=TaskResponse)
    def get_task(task_id: str) -> TaskResponse:
        record = tasks.get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        return TaskResponse(
            task_id=record.task_id,
            status=record.status,
            phase=record.phase,
            content=record.result.get("content", ""),
            review=record.result.get("review", ""),
            error=record.error,
            tool_calls=record.result.get("tool_calls", []),
            assets=record.result.get("assets", []),
            trace=list(record.trace),
            teaching=record.result.get("teaching"),
            payload=record.result.get("payload"),
        )

    # ================= 教学会话状态 =================

    @app.get("/teaching/state", response_model=TeachingStateResponse)
    def teaching_state(session_id: str, user_id: str) -> TeachingStateResponse:
        """当前会话的教学状态（主题/阶段/难度/最近一题），前端教学条渲染用。"""
        state = orchestrator._teaching.get_or_create(session_id, user_id)
        pub = orchestrator._teaching_public(state)
        return TeachingStateResponse(
            session_id=pub["session_id"],
            user_id=state["user_id"],
            stage=pub["stage"],
            depth=pub["depth"],
            topics=pub["topics"],
            consecutive_correct=pub["consecutive_correct"],
            consecutive_incorrect=pub["consecutive_incorrect"],
            last_quiz=pub["last_quiz"],
            topic_done=pub.get("topic_done", False),
            topic_finished=pub.get("topic_finished", False),
        )

    @app.get("/teaching/difficulty-curve")
    def teaching_difficulty_curve(session_id: str, user_id: str) -> dict:
        """动态难度曲线：作答顺序的难度点 + 当前状态（即将升难/降维解释中/已答完可挑战5星沙盒）。"""
        return orchestrator.difficulty_curve(user_id, session_id)


    # ================= 训练 =================

    @app.get("/mastery/state")
    def mastery_state(user_id: str, node_id: str = "") -> dict:
        """某技能点掌握度明细（客观/管家主观/沙盒/画像 + 综合分）。"""
        ms = MasteryService(plugin, store)
        if not node_id:
            return {"error": "node_id required"}
        return ms.skill_mastery(user_id, node_id)

    @app.post("/mastery/assess")
    def mastery_assess(request: MasteryAssessRequest) -> dict:
        """写入一次评估（kind=concierge 管家主观 / sandbox 沙盒[预留] / baseline 初试画像[预留]）。"""
        ms = MasteryService(plugin, store)
        return ms.assess(request.user_id, request.node_id, request.kind, request.score, request.note)


    @app.post("/training/quizzes", response_model=QuizResponse)
    def create_quiz(request: QuizRequest) -> QuizResponse:
        return QuizResponse(
            questions=training.generate_quiz(
                knowledge_point_ids=request.knowledge_point_ids,
                difficulty=request.difficulty,
                book=request.book,
                chapter=request.chapter,
                limit=request.limit,
            )
        )

    @app.post("/training/random", response_model=QuizResponse)
    def random_quiz(request: QuizRequest) -> QuizResponse:
        return QuizResponse(
            questions=training.random_quiz(
                n=request.limit or 5,
                knowledge_point_ids=request.knowledge_point_ids or None,
                difficulty=request.difficulty or None,
                book=request.book,
                chapter=request.chapter,
            )
        )

    @app.post("/training/submissions", response_model=SubmissionResponse)
    def submit_training(request: SubmissionRequest) -> SubmissionResponse:
        try:
            result = training.submit(
                user_id=request.user_id,
                question_id=request.question_id,
                answer=request.answer,
            )
            if not result.correct:
                try:
                    assets_svc.sync_wrong_book(request.user_id, training.wrong_answers(request.user_id))
                except Exception:
                    pass
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        report = training.get_mastery(request.user_id)
        adjustment = training.check_dynamic_thresholds(request.user_id)
        return SubmissionResponse(
            submission=result,
            correct=result.correct,
            mastery_report=report.model_dump(mode="json"),
            adjustment=adjustment,
        )

    # ================= 错题本 =================

    @app.get("/training/wrong-answers")
    def wrong_answers(user_id: str, limit: int = 100) -> dict:
        """错题本：记录做错的题目与用户错误选项（反馈/复习用）。"""
        items = training.wrong_answers(user_id, limit=limit)
        stats = training.wrong_answer_stats(user_id)
        return {"user_id": user_id, "total": stats["total"],
                "by_skill": stats["by_skill"], "items": items}

    @app.delete("/training/wrong-answers")
    def delete_wrong_answer(user_id: str, question_id: str) -> dict:
        """移除一道错题（已掌握后清除）。"""
        return {"ok": training.delete_wrong_answer(user_id, question_id),
                "user_id": user_id, "question_id": question_id}

    # ================= 画像 / 报告 =================

    @app.post("/profiles", response_model=ProfileResponse)
    def create_profile(request: ProfileCreateRequest) -> ProfileResponse:
        profile = profile_agent.generate_profile(
            user_id=request.user_id,
            background=request.background,
            target_role=request.target_role,
            current_level=request.current_level,
        )
        store.save_learner_profile(profile)
        # 沉淀为长期记忆
        memory.add_memory(
            request.user_id, "background", f"背景：{request.background[:120]}",
            importance=0.7,
        )
        if request.target_role:
            memory.add_memory(
                request.user_id, "goal", f"目标：{request.target_role}",
                importance=0.9,
            )
        return ProfileResponse(profile=profile)

    @app.post("/training/report", response_model=TrainingReportResponse)
    def get_training_report(request: TrainingReportRequest) -> TrainingReportResponse:
        report = training_analyzer.run(user_id=request.user_id)
        # 报告同时落为学习中心文件资产
        weak_titles = [orchestrator._skill_title(kp) for kp in report.weak_points]
        report_text = (
            "## 学习进度报告\n\n"
            f"薄弱知识点：{'、'.join(weak_titles) if weak_titles else '暂无'}\n\n"
            f"下一步建议：{report.recommended_action}\n\n"
            f"已学习技能点：{len(report.knowledge_point_scores)} / {plugin.stats().get('skills', 3796)}"
        )
        assets_svc.create(
            user_id=request.user_id,
            title="学习进度报告",
            content=report_text,
            asset_type="report",
            source_tool="training_report",
        )
        return TrainingReportResponse(report=report)

    @app.post("/training/plan")
    def generate_plan(request: TrainingReportRequest) -> dict:
        """生成个性化备考计划（画像 + 掌握度缺口 + 记忆）。"""
        user_id = request.user_id
        profile = store.get_learner_profile(user_id)
        mastery = training.get_mastery(user_id)
        weak_titles = [orchestrator._skill_title(kp) for kp in mastery.weak_points]
        memories = memory.list_memories(user_id, limit=8)
        plan = orchestrator._planner.run(
            user_id=user_id,
            profile=profile,
            weak_points=mastery.weak_points,
            weak_point_titles=weak_titles,
            mastered_count=len(mastery.knowledge_point_scores),
            total_skills=plugin.stats().get("skills", 3796),
            recent_memories=memories,
        )
        # 计划同时落为学习中心文件资产
        assets_svc.create(
            user_id=user_id,
            title="个性化备考计划",
            content=plan,
            asset_type="plan",
            source_tool="training_plan",
        )
        return {"plan": plan, "weak_point_titles": weak_titles}

    @app.get("/progress/{user_id}", response_model=ProgressResponse)
    def get_progress(user_id: str) -> ProgressResponse:
        profile = store.get_learner_profile(user_id)
        records = store.get_progress_records(user_id, plugin.manifest["plugin_id"])
        mastery = training.get_mastery(user_id)
        return ProgressResponse(
            profile=profile,
            progress=records,
            mastery_report=mastery,
        )

    # ================= 知识库浏览 =================

    @app.get("/knowledge/books")
    def list_books():
        return {"books": plugin.list_books(), "stats": plugin.stats()}

    @app.get("/knowledge/tree")
    def knowledge_tree():
        from brain_of_cloud.knowledge.catalog import build_tree
        return {"tree": build_tree(plugin.knowledge_base)}

    @app.get("/knowledge/guides")
    def knowledge_guides():
        from brain_of_cloud.knowledge.catalog import build_chapter_guides
        guides = build_chapter_guides(plugin.knowledge_base)
        return {"guides": [g.to_dict() for g in guides]}

    @app.get("/knowledge/skills/{skill_id}", response_model=SkillDetail)
    def skill_detail(skill_id: str) -> SkillDetail:
        skill = plugin.get_skill(skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"技能点不存在: {skill_id}")
        questions = plugin.questions(knowledge_point_ids=[skill_id])
        return SkillDetail(
            id=skill.id,
            title=skill.title,
            content=skill.content,
            keywords=skill.keywords,
            categories=skill.categories,
            difficulty=skill.difficulty,
            status=skill.status,
            book=skill.book_title,
            chapter=skill.chapter_title,
            section=skill.section_title,
            path=skill.path_titles,
            questions=questions,
        )

    @app.get("/knowledge/search", response_model=SearchResponse)
    def search_knowledge(
        q: str,
        top_k: int = 5,
        book: str | None = None,
        chapter: str | None = None,
    ) -> SearchResponse:
        evidence = plugin.search(
            query=q,
            top_k=max(top_k, 1),
        )
        hits = []
        for e in evidence:
            skill = plugin.get_skill(e.chunk_id)
            hits.append(
                {
                    "skill_id": e.chunk_id,
                    "title": skill.title if skill else e.chunk_id,
                    "content": e.content,
                    "source": e.source,
                    "trust": e.trust_score,
                    "difficulty": skill.difficulty if skill else 3,
                }
            )
        # 简单的前端过滤（后端 search 已按相关性排序，这里仅按参数粗过滤）
        if book:
            hits = [h for h in hits if h["source"].startswith(book)]
        if chapter:
            hits = [h for h in hits if chapter in h["source"]]
        return SearchResponse(query=q, count=len(hits), results=hits[:top_k])

    @app.get("/knowledge/questions", response_model=QuestionBrowseResponse)
    def browse_questions(
        book: str | None = None,
        chapter: str | None = None,
        difficulty: str | None = None,
        knowledge_point_ids: str | None = None,
        limit: int = 20,
    ) -> QuestionBrowseResponse:
        kp_ids = knowledge_point_ids.split(",") if knowledge_point_ids else None
        questions = plugin.questions_filtered(
            knowledge_point_ids=kp_ids,
            book=book,
            chapter=chapter,
            difficulty=difficulty,
            limit=limit,
        )
        return QuestionBrowseResponse(total=len(questions), questions=questions)

    # ================= 用户状态（个性化） =================

    @app.get("/users/{user_id}/state", response_model=UserStateResponse)
    def user_state(user_id: str) -> UserStateResponse:
        profile = store.get_learner_profile(user_id)
        mastery = training.get_mastery(user_id)
        records = store.get_progress_records(user_id, plugin.manifest["plugin_id"])
        memories = memory.list_memories(user_id, limit=15)
        weak_titles = [orchestrator._skill_title(kp) for kp in mastery.weak_points]
        stats = {
            "total_skills": plugin.stats().get("skills", 0),
            "attempted_skills": len(mastery.knowledge_point_scores),
            "mastered_skills": sum(
                1 for s in mastery.knowledge_point_scores.values() if s >= 0.7
            ),
            "weak_skills": len(mastery.weak_points),
            "questions_answered": len(records),
        }
        return UserStateResponse(
            user_id=user_id,
            profile=profile,
            memories=memories,
            mastery=mastery,
            weak_point_titles=weak_titles,
            progress=records,
            stats=stats,
        )

    # ================= 文件资产（学习中心） =================

    @app.post("/assets/wrong-book")
    def sync_wrong_book_asset(user_id: str) -> dict:
        """把当前错题整理成「错题本」文件资产（幂等刷新，供知识库文件资产区展示）。"""
        asset = assets_svc.sync_wrong_book(user_id, training.wrong_answers(user_id))
        return {"ok": True, "asset": asset}

    @app.get("/users/{user_id}/assets", response_model=AssetListResponse)
    def list_assets(user_id: str, asset_type: str | None = None, limit: int | None = None) -> AssetListResponse:
        """列出用户在学习过程中生成的文件资产，可按类型过滤。"""
        # ── 旧版「易错题合集文件」迁移为「每道错题一张卡片」（幂等） ──
        try:
            if asset_type in (None, "wrong_book"):
                assets_svc.migrate_legacy_wrong_book(
                    user_id, training.wrong_answers(user_id)
                )
        except Exception:
            pass
        rows = assets_svc.list(user_id, asset_type=asset_type, limit=limit)
        return AssetListResponse(total=len(rows), assets=rows)

    @app.get("/assets/{asset_id}", response_model=AssetDetailResponse)
    def asset_detail(asset_id: str) -> AssetDetailResponse:
        asset = assets_svc.get(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"资产不存在: {asset_id}")
        return AssetDetailResponse(
            asset_id=asset["asset_id"],
            title=asset["title"],
            asset_type=asset["asset_type"],
            content=asset["content"],
            source_tool=asset["source_tool"],
            session_id=asset["session_id"],
            created_at=asset["created_at"],
        )

    @app.delete("/assets/{asset_id}")
    def delete_asset(asset_id: str) -> dict:
        if not assets_svc.delete(asset_id):
            raise HTTPException(status_code=404, detail=f"资产不存在: {asset_id}")
        return {"status": "ok", "asset_id": asset_id}

    # ================= 数据合规（导出 / 删除，差距项 T7） =================

    @app.get("/users/{user_id}/export")
    def export_user_data(user_id: str) -> dict:
        """导出用户全部学习数据（画像/记忆/掌握度/答题/资产/会话）。"""
        return store.export_user_data(user_id, plugin.manifest["plugin_id"])

    @app.delete("/users/{user_id}/data")
    def delete_user_data(user_id: str) -> dict:
        """删除该用户全部个人数据（撤回授权）。"""
        store.delete_user_data(user_id, plugin.manifest["plugin_id"])
        return {"status": "ok", "user_id": user_id}

    # ================= 知识技能树（从知识库派生 + 节点名精确检索） =================

    @app.get("/skills/{user_id}/knowledge-tree")
    def knowledge_skill_tree(user_id: str) -> dict:
        """知识技能树：从知识库结构直接派生，节点=知识库节点，按子树技能点平均掌握度点亮（无 kw 映射）。"""
        from brain_of_cloud.services.knowledge_skill_tree import KnowledgeSkillTreeService
        svc = KnowledgeSkillTreeService(store)
        return svc.get_tree(user_id, plugin=plugin)

    @app.get("/knowledge/tree-search")
    def knowledge_tree_search(q: str) -> dict:
        """按技能树节点显示名精确检索知识库：命中节点 -> 返回子树技能点（结构精确命中，非模糊 kw）。"""
        from brain_of_cloud.services.knowledge_skill_tree import KnowledgeSkillTreeService
        svc = KnowledgeSkillTreeService(store)
        return svc.structural_search(q, plugin.knowledge_base)

    # ================= 对话式沙盒 =================

    def owned_sandbox(session_id: str, user_id: str):
        try:
            session = sandbox.get_session(session_id)
        except SandboxError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="会话属于其它账户")
        return session

    @app.post("/sandbox/tasks/start")
    def sandbox_start_task(request: SandboxSessionCreateRequest):
        tid = tasks.submit(sandbox.start_session, result_builder=lambda value: {"payload": value},
                           user_id=request.user_id, template_id=request.template_id, mode=request.mode,
                           language=request.language or None, voice=request.voice or None, trace_cb=None)
        return {"task_id": tid}

    @app.post("/sandbox/sessions/{session_id}/messages/tasks")
    def sandbox_message_task(session_id: str, request: SandboxSendMessageRequest):
        owned_sandbox(session_id, request.user_id)
        tid = tasks.submit(sandbox.send_message, result_builder=lambda value: {"payload": value},
                           session_id=session_id, user_text=request.content, trace_cb=None)
        return {"task_id": tid}

    @app.post("/sandbox/sessions/{session_id}/end/tasks")
    def sandbox_end_task(session_id: str, request: SandboxEndRequest):
        owned_sandbox(session_id, request.user_id)
        tid = tasks.submit(sandbox.end_session, result_builder=lambda value: {"payload": value},
                           session_id=session_id, user_id=request.user_id, trace_cb=None)
        return {"task_id": tid}

    @app.get("/sandbox/templates")
    def sandbox_templates(mode: str | None = None):
        """可用沙盒场景模板（前端渲染场景卡）。"""
        return {"templates": sandbox.list_templates(mode=mode)}

    @app.post("/sandbox/sessions", response_model=SandboxSessionResponse)
    def sandbox_create_session(request: SandboxSessionCreateRequest) -> SandboxSessionResponse:
        """创建沙盒会话：随机游客人设 + 开场白。"""
        try:
            return sandbox.start_session(
                user_id=request.user_id,
                template_id=request.template_id,
                mode=request.mode,
                language=request.language or None,
                voice=request.voice or None,
            )
        except SandboxError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/sandbox/sessions/{session_id}", response_model=SandboxSessionResponse)
    def sandbox_get_session(session_id: str) -> SandboxSessionResponse:
        """恢复沙盒会话状态（刷新/重进）。"""
        try:
            return sandbox.get_session(session_id)
        except SandboxError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/sandbox/sessions/{session_id}/messages", response_model=SandboxMessageResult)
    def sandbox_send_message(
        session_id: str,
        request: SandboxSendMessageRequest,
    ) -> SandboxMessageResult:
        """用户以导游身份发言，游客 Agent 实时角色扮演回复。"""
        try:
            return sandbox.send_message(session_id, request.content)
        except SandboxError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/sandbox/sessions/{session_id}/voice-messages")
    def sandbox_voice_messages(
        session_id: str,
        request: SandboxVoiceMessagesRequest,
    ) -> SandboxSessionResponse:
        """实时语音台词落库：导游/游客台词追加进会话（不触发游客 Agent）。"""
        try:
            return sandbox.append_voice_messages(
                session_id,
                user_id=request.user_id,
                messages=request.messages,
            )
        except SandboxError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/sandbox/sessions/{session_id}/end", response_model=SandboxSessionResponse)
    def sandbox_end_session(
        session_id: str,
        request: SandboxEndRequest,
    ) -> SandboxSessionResponse:
        """结束沙盒：五维评估 + 关联技能点 + 落学习中心报告。"""
        try:
            return sandbox.end_session(session_id, user_id=request.user_id)
        except SandboxError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/sandbox/users/{user_id}/records")
    def sandbox_user_records(user_id: str):
        """用户历史沙盒场次（训练场统计）。"""
        return {"records": sandbox.list_user_records(user_id)}

    # ================= 景区讲解 · 语音实训（/voice/*） =================
    # 说明：独立于沙盒对话模块；录音 -> Whisper 转写 -> 对照景区知识打分。
    # 预留扩展：scene.panorama（720云 全景）/ scene.hotspots（热点对应讲解点）
    # 已由 scenes 数据承载，前端接入 iframe 后无需改接口。

    @app.get("/voice/scenes")
    def voice_scenes() -> dict:
        return {"scenes": list_scenes()}

    @app.post("/voice/transcribe")
    def voice_transcribe(file: UploadFile = File(...)) -> dict:
        """上传音频 -> Whisper 转写（wav/mp3/m4a/webm/ogg...）。"""
        import tempfile
        from pathlib import Path as _P

        suffix = _P(file.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file.file.read())
            tmp_path = tmp.name
        try:
            return transcribe_audio(tmp_path)
        finally:
            try:
                import os as _os
                _os.unlink(tmp_path)
            except OSError:
                pass

    @app.post("/voice/evaluate")
    def voice_evaluate(payload: dict) -> dict:
        """{scene_id, transcript, hotspot_id?} -> 要点覆盖 + AI 评价报告。

        hotspot_id 用于 720云 全景热点场景：AI 打分时知道学员当前在哪个热点。
        """
        scene = get_scene(str(payload.get("scene_id", "")))
        if scene is None:
            raise HTTPException(status_code=404, detail="未知讲解场景")
        transcript = str(payload.get("transcript", "") or "")
        hotspot_id = payload.get("hotspot_id")
        report = evaluate_scene(
            scene,
            transcript,
            hotspot_id=str(hotspot_id) if hotspot_id else None,
            llm_client=llm_client,
        )
        return {"scene": scene, "transcript": transcript, "report": report}

    # ================= 实时语音 · Qwen Realtime 中继（沙盒语音） =================
    # 浏览器(16k PCM) -> 后端 -> Qwen realtime；模型 24k PCM/转写/事件 -> 浏览器。
    # 会话需先经 POST /sandbox/sessions 创建（可选 language/voice）。

    async def _voice_relay_send(ws: WebSocket, q: "asyncio.Queue[dict]") -> None:
        while True:
            ev = await q.get()
            try:
                await ws.send_text(json.dumps(ev, ensure_ascii=False))
            except Exception:
                break

    @app.websocket("/voice/realtime/{session_id}")
    async def voice_realtime_ws(websocket: WebSocket, session_id: str, user_id: str = "") -> None:
        await websocket.accept()
        loop = asyncio.get_running_loop()
        ev_q: asyncio.Queue[dict] = asyncio.Queue()
        client = None
        sender = None
        try:
            full = store.get_sandbox_session(session_id)
            if full is None:
                raise HTTPException(status_code=404, detail="未知沙盒会话")
            if user_id and full.get("user_id") and user_id != full.get("user_id"):
                raise HTTPException(status_code=403, detail="user_id 与会话不匹配")
            if full.get("status") != "active":
                raise HTTPException(status_code=400, detail="会话已结束，无法语音")
            template = sandbox.get_template(full["template_id"])
            state = full.get("state") or {}
            customer = full.get("customer") or {}  # 完整人设（含 hidden，供游客扮演）
            lang = str(state.get("voice_lang") or "") or "en"
            voice = str(state.get("voice_name") or "")

            from brain_of_cloud.services.language_profiles import pick_voice
            from brain_of_cloud.voice.realtime_qwen import (
                QwenRealtimeClient,
                build_sandbox_voice_instructions,
                resolve_env,
            )

            if not voice:
                voice = pick_voice(lang, customer.get("gender", ""))
            stage_index = int(state.get("stage", 0) or 0)
            instructions = build_sandbox_voice_instructions(template, customer, lang, stage_index)
            api_key, url, model = resolve_env()

            def _push(ev: dict) -> None:
                loop.call_soon_threadsafe(ev_q.put_nowait, ev)

            client = QwenRealtimeClient(api_key, url, model, instructions,
                                        voice=voice, on_event=_push)
            await websocket.send_text(json.dumps({
                "type": "session.meta",
                "session_id": session_id,
                "template_id": template.template_id,
                "title": template.title,
                "language": lang,
                "voice": voice,
                "customer": {k: customer.get(k) for k in ("name", "nationality", "age", "gender")},
                "stage_index": stage_index,
            }, ensure_ascii=False))
            client.connect()
            if not client.wait_ready(20):
                raise RuntimeError("Qwen realtime 连接超时或会话未确认，请检查 DASHSCOPE_API_KEY / QWEN_OMNI_WS_URL / QWEN_OMNI_MODEL")
            await websocket.send_text(json.dumps({"type": "ready"}, ensure_ascii=False))

            sender = asyncio.create_task(_voice_relay_send(websocket, ev_q))
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                mtype = str(data.get("type", ""))
                try:
                    if mtype == "audio":
                        audio = base64.b64decode(str(data.get("audio", "")) or "")
                        client.append_audio(audio)
                    elif mtype == "text":
                        client.ask_text(str(data.get("text", "")))
                    elif mtype == "commit":
                        client.commit()
                    elif mtype == "cancel":
                        client.cancel_response()
                    elif mtype == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except Exception as exc:
                    await websocket.send_text(json.dumps({
                        "type": "error", "error": {"message": "上行失败: " + str(exc)},
                    }, ensure_ascii=False))
        except WebSocketDisconnect:
            pass
        except HTTPException as exc:
            try:
                await websocket.send_text(json.dumps({
                    "type": "error", "error": {"message": exc.detail},
                }, ensure_ascii=False))
            except Exception:
                pass
        except Exception as exc:  # noqa: BLE001
            try:
                await websocket.send_text(json.dumps({
                    "type": "error", "error": {"message": str(exc)},
                }, ensure_ascii=False))
            except Exception:
                pass
        finally:
            if sender is not None:
                sender.cancel()
            if client is not None:
                client.close()

    @app.get("/voice/realtime-test")
    def voice_realtime_test_page():
        """浏览器端链路测试页（麦克风 -> 后端 -> Qwen realtime -> 播放）。"""
        page = Path(__file__).resolve().parent.parent / "voice" / "realtime_test.html"
        if not page.is_file():
            raise HTTPException(status_code=404, detail="测试页缺失: brain_of_cloud/voice/realtime_test.html")
        from fastapi.responses import FileResponse, HTMLResponse

        return HTMLResponse(page.read_text(encoding="utf-8"))

    # ================= 学习翻译 / 多语种发音 =================

    @app.post("/voice/translate")
    def voice_translate(payload: dict) -> dict:
        """文字 AI 翻译：mode=plain 普通文本 / markdown 保留 Markdown 结构。"""
        text = str(payload.get("text", "") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="text 不能为空")
        if len(text) > 12000:
            raise HTTPException(status_code=400, detail="文本过长（限 12000 字符）")
        lang = str(payload.get("lang") or "en").strip() or "en"
        mode = str(payload.get("mode") or "plain").strip()
        if mode not in ("plain", "markdown"):
            mode = "plain"
        from brain_of_cloud.services.language_profiles import LANG_NAMES_EN

        lang_en = LANG_NAMES_EN.get(lang, lang)
        if mode == "markdown":
            system = (
                "你是一名面向导游培训的翻译。请把用户提供的 Markdown 文档翻译成"
                + lang_en + "（" + lang + "）。要求：保留 Markdown 结构与格式"
                "（标题/列表/加粗/表格/代码块），保留专有名词、地名、机构名、占位符"
                "与已用英文书写的术语不译，只翻译正文；输出仍为合法 Markdown，"
                "不要输出任何解释。"
            )
        else:
            system = (
                "你是一名面向导游培训的翻译。请把用户提供的文本翻译成"
                + lang_en + "（" + lang + "）。口语自然、术语准确；"
                "不要解释、不要输出译文以外的内容。"
            )
        resp = llm_client.generate(system, text, temperature=0.2, max_tokens=8192)
        return {"translated": (resp.content or "").strip(), "lang": lang, "mode": mode}

    @app.post("/voice/speak")
    def voice_speak(payload: dict) -> dict:
        """多语种发音：把给定文本用目标语言朗读（复用 Qwen realtime 一次性合成）。"""
        text = str(payload.get("text", "") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="text 不能为空")
        if len(text) > 4000:
            raise HTTPException(status_code=400, detail="单次朗读文本过长（限 4000 字符），建议分段")
        lang = str(payload.get("lang") or "en").strip() or "en"
        import base64 as _b64

        from brain_of_cloud.voice.realtime_qwen import speak_text

        res = speak_text(text, lang=lang, voice=(payload.get("voice") or None))
        return {
            "audio_b64": _b64.b64encode(res["audio"]).decode("ascii"),
            "transcript": res["transcript"],
            "lang": res["lang"],
            "voice": res["voice"],
        }

    # ================= 会话管理 =================

    @app.get("/sessions")
    def list_sessions(user_id: str) -> dict:
        """用户历史对话列表（标题/消息数/最后活跃时间）。"""
        return {"sessions": store.list_sessions(user_id)}

    @app.get("/sessions/{session_id}/messages")
    def session_messages(session_id: str) -> dict:
        """单个历史会话的消息记录（role/content）。"""
        return {"messages": store.get_session_messages(session_id)}

    @app.delete("/sessions/{session_id}")
    def clear_session(session_id: str) -> dict:
        orchestrator.clear_session(session_id)
        return {"status": "ok", "session_id": session_id}

    # ── 初试引导 / 学习路径规划（M1b） ──
    from brain_of_cloud.api.onboarding import create_onboarding_router
    app.include_router(create_onboarding_router(plugin, store, llm_client))

    return app







