from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from brain_of_cloud.domain.models import (
    LearnerProfile,
    MasteryReport,
    ProgressRecord,
    Question,
    SubmissionResult,
)


class MessageRequest(BaseModel):
    user_id: str
    session_id: str
    content: str
    knowledge_point_id: str | None = None  # 硬挂钩：指定本次教学聚焦的技能点 id


class MessageResponse(BaseModel):
    task_id: str
    status: str
    content: str = ""
    review: str = ""


class TaskResponse(BaseModel):
    task_id: str
    status: str
    phase: str = "queued"
    content: str = ""
    review: str = ""
    error: str = ""
    tool_calls: list[str] = []
    assets: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []  # 实时多 Agent 工作轨迹（agent_trace）
    teaching: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None  # 实战异步任务结果；原对话响应保持兼容



class MasteryAssessRequest(BaseModel):
    """写入一次掌握度评估（管家主观 / 沙盒 / 初试画像共用）。"""
    user_id: str
    node_id: str
    kind: str = 'concierge'
    score: float = 0
    note: str = ''


class TeachingStateResponse(BaseModel):
    """教学会话状态（一对一教学闭环：主题/阶段/难度/最近一题）。"""
    session_id: str
    user_id: str
    stage: str = "goal_setting"
    depth: str = "intro"
    topics: list[dict[str, Any]] = []
    consecutive_correct: int = 0
    consecutive_incorrect: int = 0
    last_quiz: dict[str, Any] | None = None
    topic_done: bool = False
    topic_finished: bool = False


# ---- 文件资产 ----

class AssetListResponse(BaseModel):
    total: int
    assets: list[dict[str, Any]] = []


class AssetDetailResponse(BaseModel):
    asset_id: str
    title: str
    asset_type: str
    content: str
    source_tool: str = ""
    session_id: str = ""
    created_at: str = ""


class QuizRequest(BaseModel):
    knowledge_point_ids: list[str] = Field(default_factory=list)
    difficulty: str = ""
    book: str | None = None
    chapter: str | None = None
    limit: int | None = None


class QuizResponse(BaseModel):
    questions: list[Question]


class SubmissionRequest(BaseModel):
    user_id: str
    question_id: str
    answer: str


class SubmissionResponse(BaseModel):
    submission: SubmissionResult
    correct: bool
    mastery_report: dict
    adjustment: dict = Field(default_factory=lambda: {"action": "maintain", "knowledge_point_ids": []})


class ProfileCreateRequest(BaseModel):
    user_id: str
    background: str
    target_role: str = "导游资格证"
    current_level: str = "intro"


class ProfileResponse(BaseModel):
    profile: LearnerProfile


class TrainingReportRequest(BaseModel):
    user_id: str


class TrainingReportResponse(BaseModel):
    report: MasteryReport


class ProgressResponse(BaseModel):
    profile: LearnerProfile | None = None
    progress: list[ProgressRecord] = []
    mastery_report: MasteryReport | None = None


# ---- 知识库浏览 ----

class SkillDetail(BaseModel):
    id: str
    title: str
    content: str
    keywords: list[str] = []
    categories: list[str] = []
    difficulty: int = 3
    status: str = "locked"
    book: str = ""
    chapter: str = ""
    section: str = ""
    path: list[str] = []
    questions: list[Question] = []


class SearchHit(BaseModel):
    skill_id: str
    title: str
    content: str
    source: str
    trust: float
    difficulty: int = 3


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[SearchHit]


class QuestionBrowseResponse(BaseModel):
    total: int
    questions: list[Question]


class UserStateResponse(BaseModel):
    user_id: str
    profile: LearnerProfile | None = None
    memories: list[dict[str, Any]] = []
    mastery: MasteryReport | None = None
    weak_point_titles: list[str] = []
    progress: list[ProgressRecord] = []
    stats: dict[str, Any] = {}


# ---- 对话式沙盒 ----

class SandboxTemplateItem(BaseModel):
    template_id: str
    mode: str
    title: str
    location: str
    task: str
    difficulty: int
    category: str
    opening: str = ""
    stage_titles: list[str] = []
    stage_count: int = 0


class SandboxSessionCreateRequest(BaseModel):
    user_id: str
    template_id: str
    mode: str | None = None
    # 语音/外语训练：语言码（en/ja/de/...，空=传统文字沙盒）+ 指定音色（空=按语言+人设性别自动选）
    language: str = ""
    voice: str = ""


class SandboxSendMessageRequest(BaseModel):
    user_id: str
    content: str


class SandboxEndRequest(BaseModel):
    user_id: str


class SandboxVoiceMessagesRequest(BaseModel):
    user_id: str
    messages: list[dict] = []  # [{role: guide|customer, content: str}]


class SandboxSessionResponse(BaseModel):
    session_id: str
    user_id: str
    mode: str
    template_id: str
    language: str = ""
    voice: str = ""
    customer: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []
    stage: dict[str, Any] = {}
    template: dict[str, Any] = {}
    status: str = "active"
    scene_complete: bool = False
    scene_outcome: str | None = None  # success 达成目标 / failed 搞砸了 / abandoned 手动结束 / null 进行中
    scene_fail_reason: str | None = None
    score: float | None = None
    dims: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None
    created_at: str = ""
    ended_at: str | None = None


class SandboxMessageResult(BaseModel):
    reply: str
    mood: str = "一般"
    stage: int = 0
    stage_total: int = 0
    stage_title: str = ""
    stage_advanced: bool = False
    stage_tip: dict[str, Any] | None = None
    scene_complete: bool = False
    scene_outcome: str | None = None
    scene_fail_reason: str | None = None


class SandboxRecordItem(BaseModel):
    session_id: str
    mode: str
    template_id: str
    title: str
    score: float | None = None
    dims: dict[str, Any] | None = None
    scene_outcome: str | None = None
    ended_at: str | None = None



