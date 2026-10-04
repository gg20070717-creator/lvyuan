from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentId(StrEnum):
    CONCIERGE = "concierge"
    PROFILE = "profile"
    RETRIEVAL = "retrieval"
    TRAINING_ANALYZER = "training_analyzer"
    TEXT_GENERATOR = "text_generator"
    LEARNING_PLANNER = "learning_planner"
    CHART_GENERATOR = "chart_generator"
    HTML_DEMO_GENERATOR = "html_demo_generator"
    IMAGE_GENERATOR = "image_generator"
    BLUE_HAT = "blue_hat"
    WHITE_HAT = "white_hat"
    GREEN_HAT = "green_hat"
    YELLOW_HAT = "yellow_hat"
    BLACK_HAT = "black_hat"
    RED_HAT = "red_hat"
    ESSAY_QUESTION = "essay_question"
    SCENE_DIRECTOR = "scene_director"
    CUSTOMER_GENERATOR = "customer_generator"


class Visibility(StrEnum):
    PRIVATE = "private"
    GROUP = "group"
    USER = "user"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AssetType(StrEnum):
    LECTURE = "lecture"  # 讲义 / 考点总结 / 学习材料
    PRACTICE_GUIDE = "practice_guide"  # 实操指南 / 答题模板
    GRADED_QUIZ = "graded_quiz"  # 测试 / 真题卷
    TEXT = "text"  # 其他文本
    PLAN = "plan"  # 个性化备考计划
    REPORT = "report"  # 学习进度报告
    WRONG_BOOK = "wrong_book"  # 错题本（错题汇总，格式与文件资产一致）


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Asset(StrictModel):
    """学习中心里的文件资产 — 用户在使用过程中生成的可管理文件。"""

    asset_id: str
    user_id: str
    session_id: str = ""
    title: str
    asset_type: AssetType = AssetType.TEXT
    content: str
    source_tool: str = ""
    evidence_ids: list[str] = Field(default_factory=list)  # 结构化引用链（T14）：生成依据的知识片段
    created_at: str = ""


class Mention(StrictModel):
    agent_id: AgentId
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)


class Message(StrictModel):
    message_id: str
    task_id: str
    from_agent: AgentId
    content: str
    lsn: int = Field(ge=1)
    visibility: Visibility = Visibility.GROUP
    mentions: list[Mention] = Field(default_factory=list)


class Task(StrictModel):
    task_id: str
    user_id: str
    session_id: str
    plugin_id: str
    status: TaskStatus = TaskStatus.CREATED
    current_round: int = Field(default=0, ge=0)
    max_rounds: int = Field(default=3, ge=1)


class AgentRun(StrictModel):
    run_id: str
    task_id: str
    agent_id: AgentId
    status: RunStatus = RunStatus.PENDING
    input_message_ids: list[str] = Field(default_factory=list)
    output_message_id: str | None = None
    attempts: int = Field(default=0, ge=0)
    error: str | None = None


class KnowledgePoint(StrictModel):
    id: str
    name: str
    level: str
    prerequisites: list[str] = Field(default_factory=list)
    target_skill: str


class Evidence(StrictModel):
    chunk_id: str
    content: str
    source: str
    trust_score: float = Field(ge=0, le=1)
    knowledge_point_ids: list[str]


class Question(StrictModel):
    question_id: str
    knowledge_point_id: str
    difficulty: str
    difficulty_level: int | None = None  # 题库难度 1-5
    prompt: str
    answer_key: str = ""
    rubric: str = ""
    misconception_tags: list[str] = Field(default_factory=list)
    # 四选一客观题支持（题库真题）：选项列表 + 正确字母 + 解析
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    source: str = ""  # 出处定位（书/章/节/技能点）


class SubmissionResult(StrictModel):
    submission_id: str
    user_id: str
    question_id: str
    score: float = Field(ge=0, le=1)
    correct: bool
    feedback: str
    misconception_tags: list[str] = Field(default_factory=list)


class MasteryReport(StrictModel):
    report_id: str
    user_id: str
    knowledge_point_scores: dict[str, float]
    weak_points: list[str]
    recommended_action: str


class LearnerProfile(StrictModel):
    user_id: str
    background: str
    target_role: str
    current_level: str = "intro"
    style_preferences: dict[str, str] = Field(default_factory=dict)
    baseline_scores: dict[str, float] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class ProgressRecord(StrictModel):
    user_id: str
    plugin_id: str
    knowledge_point_id: str
    mastery: float = Field(ge=0, le=1)
    attempt_count: int = Field(default=0, ge=0)
    consecutive_correct: int = Field(default=0, ge=0)
    consecutive_incorrect: int = Field(default=0, ge=0)
    last_attempted_at: str | None = None
    difficulty: str = "intro"


class AgentConfig(StrictModel):
    agent_id: AgentId
    role_group: str
    model: str = "deepseek-v4-flash-vision-exp"
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1)
    reasoning_effort: int | None = None
    system_prompt: str = ""
    max_retries: int = Field(default=3, ge=0)
