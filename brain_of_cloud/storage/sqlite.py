from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from brain_of_cloud.domain.models import (
    AgentId,
    AgentRun,
    Asset,
    AssetType,
    LearnerProfile,
    Mention,
    Message,
    ProgressRecord,
    RunStatus,
    SubmissionResult,
    Task,
    TaskStatus,
    Visibility,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    plugin_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_round INTEGER NOT NULL,
                    max_rounds INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    from_agent TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mentions_json TEXT NOT NULL,
                    lsn INTEGER NOT NULL CHECK (lsn >= 1),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_message_ids_json TEXT NOT NULL,
                    output_message_id TEXT,
                    attempts INTEGER NOT NULL,
                    error TEXT,
                    UNIQUE(task_id, message_id, agent_id),
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id),
                    FOREIGN KEY(message_id) REFERENCES messages(message_id)
                );

                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    score REAL NOT NULL,
                    correct INTEGER NOT NULL,
                    feedback TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learner_profiles (
                    user_id TEXT PRIMARY KEY,
                    background TEXT NOT NULL,
                    target_role TEXT NOT NULL,
                    current_level TEXT NOT NULL DEFAULT 'intro',
                    style_preferences_json TEXT NOT NULL DEFAULT '{}',
                    baseline_scores_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS progress_records (
                    user_id TEXT NOT NULL,
                    plugin_id TEXT NOT NULL,
                    knowledge_point_id TEXT NOT NULL,
                    mastery REAL NOT NULL CHECK (mastery >= 0 AND mastery <= 1),
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    consecutive_correct INTEGER NOT NULL DEFAULT 0,
                    consecutive_incorrect INTEGER NOT NULL DEFAULT 0,
                    last_attempted_at TEXT,
                    difficulty TEXT NOT NULL DEFAULT 'intro',
                    PRIMARY KEY (user_id, plugin_id, knowledge_point_id)
                );

                CREATE TABLE IF NOT EXISTS session_messages (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_session_messages
                    ON session_messages(session_id, seq);

                CREATE TABLE IF NOT EXISTS user_memories (
                    memory_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5,
                    source_session TEXT,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_user_memories
                    ON user_memories(user_id, created_at);

                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_tool TEXT NOT NULL DEFAULT '',
                    evidence_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_assets_user
                    ON assets(user_id, created_at);

                CREATE TABLE IF NOT EXISTS sandbox_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    template_id TEXT NOT NULL,
                    customer_json TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    score REAL,
                    dims_json TEXT,
                    feedback_json TEXT,
                    created_at TEXT,
                    ended_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sandbox_sessions_user
                    ON sandbox_sessions(user_id, created_at);

                CREATE TABLE IF NOT EXISTS teaching_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    topic_ids TEXT NOT NULL DEFAULT '[]',
                    stage TEXT NOT NULL DEFAULT 'goal_setting',
                    depth TEXT NOT NULL DEFAULT 'intro',
                    consecutive_correct INTEGER NOT NULL DEFAULT 0,
                    consecutive_incorrect INTEGER NOT NULL DEFAULT 0,
                    quiz_history TEXT NOT NULL DEFAULT '[]',
                    quiz_correct TEXT NOT NULL DEFAULT '[]',
                    last_quiz_json TEXT,
                    reteach_question_id TEXT,
                    reteach_question_json TEXT,
                    last_outcome TEXT,
                    topic_finished INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_teaching_sessions_user
                    ON teaching_sessions(user_id, updated_at);

                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_session_summaries_user
                    ON session_summaries(user_id);

                CREATE TABLE IF NOT EXISTS interaction_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    from_agent TEXT NOT NULL,
                    to_agents TEXT NOT NULL DEFAULT '[]',
                    action TEXT NOT NULL,
                    content_summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_interaction_logs_user
                    ON interaction_logs(user_id, created_at);

                CREATE TABLE IF NOT EXISTS skill_activations (
                    activation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'concierge',
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_skill_activations_user
                    ON skill_activations(user_id, node_id);

                CREATE TABLE IF NOT EXISTS wrong_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    knowledge_point_id TEXT,
                    skill_title TEXT DEFAULT '',
                    prompt TEXT NOT NULL,
                    options_json TEXT NOT NULL DEFAULT '[]',
                    user_answer TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    explanation TEXT DEFAULT '',
                    reteach_note TEXT DEFAULT '',
                    difficulty TEXT DEFAULT 'basic',
                    source TEXT DEFAULT '',
                    wrong_count INTEGER NOT NULL DEFAULT 1,
                    last_wrong_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_wrong_answers_user
                    ON wrong_answers(user_id, last_wrong_at);
                CREATE TABLE IF NOT EXISTS mastery_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'concierge',
                    score REAL NOT NULL DEFAULT 0,
                    note TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mastery_assessments_user
                    ON mastery_assessments(user_id, node_id, kind);
                CREATE TABLE IF NOT EXISTS onboarding_profiles (
                    user_id TEXT PRIMARY KEY,
                    persona_json TEXT NOT NULL DEFAULT '{}',
                    identity_answers_json TEXT NOT NULL DEFAULT '{}',
                    group_status_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learning_paths (
                    user_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    route_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'active',
                    note TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_learning_paths_user
                    ON learning_paths(user_id, created_at);
                CREATE TABLE IF NOT EXISTS onboarding_qa (
                    user_id TEXT PRIMARY KEY,
                    step INTEGER NOT NULL DEFAULT 0,
                    answers_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS profile_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    persona_json TEXT NOT NULL DEFAULT '{}',
                    source TEXT NOT NULL DEFAULT 'refresh',
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, version)
                );
                """
            )
            # ── 老库迁移：onboarding_profiles 补 insight_json（管家解读）列 ──
            ocols = {r["name"] for r in conn.execute("PRAGMA table_info(onboarding_profiles)").fetchall()}
            if "insight_json" not in ocols:
                conn.execute(
                    "ALTER TABLE onboarding_profiles ADD COLUMN insight_json TEXT NOT NULL DEFAULT '{}'"
                )
            # ── 老库迁移（T14）：assets 表补 evidence_ids_json 列 ──
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(assets)").fetchall()}
            if "evidence_ids_json" not in cols:
                conn.execute(
                    "ALTER TABLE assets ADD COLUMN evidence_ids_json TEXT NOT NULL DEFAULT '[]'"
                )
            # ── 老库迁移：teaching_sessions 补 quiz_correct_json 列（重复答对换新题用）──
            tcols = {r["name"] for r in conn.execute("PRAGMA table_info(teaching_sessions)").fetchall()}
            if "quiz_correct" not in tcols:
                conn.execute(
                    "ALTER TABLE teaching_sessions ADD COLUMN quiz_correct TEXT NOT NULL DEFAULT '[]'"
                )
            # ── 老库迁移：teaching_sessions 补纠错重问字段（答错同题重问闭环用）──
            tcols2 = {r["name"] for r in conn.execute("PRAGMA table_info(teaching_sessions)").fetchall()}
            if "reteach_question_id" not in tcols2:
                conn.execute(
                    "ALTER TABLE teaching_sessions ADD COLUMN reteach_question_id TEXT"
                )
            if "reteach_question_json" not in tcols2:
                conn.execute(
                    "ALTER TABLE teaching_sessions ADD COLUMN reteach_question_json TEXT"
                )
            tcols3 = {r["name"] for r in conn.execute("PRAGMA table_info(teaching_sessions)").fetchall()}
            if "last_outcome" not in tcols3:
                conn.execute(
                    "ALTER TABLE teaching_sessions ADD COLUMN last_outcome TEXT"
                )
            tcols4 = {r["name"] for r in conn.execute("PRAGMA table_info(teaching_sessions)").fetchall()}
            if "topic_finished" not in tcols4:
                conn.execute(
                    "ALTER TABLE teaching_sessions ADD COLUMN topic_finished INTEGER NOT NULL DEFAULT 0"
                )
            # ── 老库迁移：wrong_answers 补降维解释字段（reteach_note）──
            wcols = {r["name"] for r in conn.execute("PRAGMA table_info(wrong_answers)").fetchall()}
            if "reteach_note" not in wcols:
                conn.execute(
                    "ALTER TABLE wrong_answers ADD COLUMN reteach_note TEXT DEFAULT ''"
                )

    def create_task(self, user_id: str, session_id: str, plugin_id: str) -> Task:
        task = Task(
            task_id=f"task_{uuid.uuid4().hex}",
            user_id=user_id,
            session_id=session_id,
            plugin_id=plugin_id,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    task.task_id,
                    task.user_id,
                    task.session_id,
                    task.plugin_id,
                    task.status.value,
                    task.current_round,
                    task.max_rounds,
                ),
            )
        return task

    def get_task(self, task_id: str) -> Task:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return Task(
            task_id=row["task_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            plugin_id=row["plugin_id"],
            status=TaskStatus(row["status"]),
            current_round=row["current_round"],
            max_rounds=row["max_rounds"],
        )

    def create_message(
        self,
        task_id: str,
        from_agent: AgentId,
        content: str,
        mentions: list[Mention] | None = None,
        visibility: Visibility = Visibility.GROUP,
    ) -> Message:
        mentions = mentions or []
        with self._connect() as conn:
            next_lsn = conn.execute(
                "SELECT COALESCE(MAX(lsn), 0) + 1 FROM messages"
            ).fetchone()[0]
            message = Message(
                message_id=f"msg_{uuid.uuid4().hex}",
                task_id=task_id,
                from_agent=from_agent,
                content=content,
                visibility=visibility,
                mentions=mentions,
                lsn=next_lsn,
            )
            conn.execute(
                "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    message.message_id,
                    task_id,
                    from_agent.value,
                    visibility.value,
                    content,
                    json.dumps(
                        [m.model_dump(mode="json") for m in mentions],
                        ensure_ascii=False,
                    ),
                    next_lsn,
                ),
            )
        return message

    def get_message(self, message_id: str) -> Message:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            raise KeyError(message_id)
        return Message(
            message_id=row["message_id"],
            task_id=row["task_id"],
            from_agent=AgentId(row["from_agent"]),
            visibility=Visibility(row["visibility"]),
            content=row["content"],
            mentions=[
                Mention.model_validate(item)
                for item in json.loads(row["mentions_json"])
            ],
            lsn=row["lsn"],
        )

    def list_messages(self, task_id: str) -> list[Message]:
        """按任务列出群组空间消息（含结构化 mentions），用于协同审计。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE task_id = ?
                ORDER BY lsn
                """,
                (task_id,),
            ).fetchall()
        return [
            Message(
                message_id=row["message_id"],
                task_id=row["task_id"],
                from_agent=AgentId(row["from_agent"]),
                visibility=Visibility(row["visibility"]),
                content=row["content"],
                mentions=[
                    Mention.model_validate(item)
                    for item in json.loads(row["mentions_json"])
                ],
                lsn=row["lsn"],
            )
            for row in rows
        ]

    def append_message_mentions(
        self,
        message_id: str,
        mentions: list[Mention],
    ) -> Message:
        """向既有消息追加结构化 mentions（工具调用后记录唤醒关系）。"""
        if not mentions:
            return self.get_message(message_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mentions_json FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise KeyError(message_id)
            existing = [
                Mention.model_validate(item)
                for item in json.loads(row["mentions_json"])
            ]
            existing_ids = {(m.agent_id.value, m.reason) for m in existing}
            merged = list(existing)
            for mention in mentions:
                key = (mention.agent_id.value, mention.reason)
                if key not in existing_ids:
                    merged.append(mention)
                    existing_ids.add(key)
            conn.execute(
                "UPDATE messages SET mentions_json = ? WHERE message_id = ?",
                (
                    json.dumps([m.model_dump(mode="json") for m in merged], ensure_ascii=False),
                    message_id,
                ),
            )
        return self.get_message(message_id)

    def enqueue_agent_run(
        self,
        task_id: str,
        message_id: str,
        agent_id: AgentId,
    ) -> AgentRun:
        with self._connect() as conn:
            message = conn.execute(
                "SELECT task_id FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if message is None:
                raise KeyError(message_id)
            if message["task_id"] != task_id:
                raise ValueError(
                    f"Message {message_id} does not belong to task {task_id}"
                )

            existing = conn.execute(
                """
                SELECT *
                FROM agent_runs
                WHERE task_id = ? AND message_id = ? AND agent_id = ?
                """,
                (task_id, message_id, agent_id.value),
            ).fetchone()
            if existing is not None:
                return self._agent_run_from_row(existing)

            run = AgentRun(
                run_id=f"run_{uuid.uuid4().hex}",
                task_id=task_id,
                agent_id=agent_id,
                input_message_ids=[message_id],
            )
            conn.execute(
                "INSERT OR IGNORE INTO agent_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.run_id,
                    task_id,
                    message_id,
                    agent_id.value,
                    run.status.value,
                    json.dumps(run.input_message_ids),
                    run.output_message_id,
                    run.attempts,
                    run.error,
                ),
            )
            existing = conn.execute(
                """
                SELECT *
                FROM agent_runs
                WHERE task_id = ? AND message_id = ? AND agent_id = ?
                """,
                (task_id, message_id, agent_id.value),
            ).fetchone()
            if existing is not None:
                return self._agent_run_from_row(existing)
        return run

    def update_task_status(self, task_id: str, status: TaskStatus) -> Task:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET status = ? WHERE task_id = ?",
                (status.value, task_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(task_id)
        return self.get_task(task_id)

    def complete_agent_run(
        self,
        run_id: str,
        output_message_id: str | None = None,
    ) -> AgentRun:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, output_message_id = ?
                WHERE run_id = ?
                """,
                (RunStatus.COMPLETED.value, output_message_id, run_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(run_id)
        return self.get_agent_run(run_id)

    def get_agent_run(self, run_id: str) -> AgentRun:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return self._agent_run_from_row(row)

    def list_agent_runs(self, task_id: str) -> list[AgentRun]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM agent_runs
                WHERE task_id = ?
                ORDER BY agent_id, run_id
                """,
                (task_id,),
            ).fetchall()
        return [self._agent_run_from_row(row) for row in rows]

    def save_submission(self, submission: SubmissionResult) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO submissions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    submission.submission_id,
                    submission.user_id,
                    submission.question_id,
                    submission.score,
                    int(submission.correct),
                    submission.feedback,
                ),
            )

    def get_submissions(self, user_id: str) -> list[SubmissionResult]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM submissions WHERE user_id = ? ORDER BY submission_id",
                (user_id,),
            ).fetchall()
        return [
            SubmissionResult(
                submission_id=row["submission_id"],
                user_id=row["user_id"],
                question_id=row["question_id"],
                score=row["score"],
                correct=bool(row["correct"]),
                feedback=row["feedback"],
            )
            for row in rows
        ]

    def save_learner_profile(self, profile: LearnerProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO learner_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.user_id,
                    profile.background,
                    profile.target_role,
                    profile.current_level,
                    json.dumps(profile.style_preferences, ensure_ascii=False),
                    json.dumps(profile.baseline_scores, ensure_ascii=False),
                    profile.created_at,
                    profile.updated_at,
                ),
            )

    def get_learner_profile(self, user_id: str) -> LearnerProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM learner_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return LearnerProfile(
            user_id=row["user_id"],
            background=row["background"],
            target_role=row["target_role"],
            current_level=row["current_level"],
            style_preferences=json.loads(row["style_preferences_json"]),
            baseline_scores=json.loads(row["baseline_scores_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save_progress_records(
        self,
        records: list[ProgressRecord],
    ) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO progress_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.user_id,
                        r.plugin_id,
                        r.knowledge_point_id,
                        r.mastery,
                        r.attempt_count,
                        r.consecutive_correct,
                        r.consecutive_incorrect,
                        r.last_attempted_at,
                        r.difficulty,
                    )
                    for r in records
                ],
            )

    def get_progress_records(
        self,
        user_id: str,
        plugin_id: str,
    ) -> list[ProgressRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM progress_records
                WHERE user_id = ? AND plugin_id = ?
                ORDER BY knowledge_point_id
                """,
                (user_id, plugin_id),
            ).fetchall()
        return [
            ProgressRecord(
                user_id=row["user_id"],
                plugin_id=row["plugin_id"],
                knowledge_point_id=row["knowledge_point_id"],
                mastery=row["mastery"],
                attempt_count=row["attempt_count"],
                consecutive_correct=row["consecutive_correct"],
                consecutive_incorrect=row["consecutive_incorrect"],
                last_attempted_at=row["last_attempted_at"],
                difficulty=row["difficulty"],
            )
            for row in rows
        ]

    # ---- 会话消息持久化（跨重启保留对话） ----

    def save_session_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
    ) -> None:
        from datetime import datetime, timezone

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_messages (session_id, user_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    role,
                    content,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_session_messages(self, session_id: str) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM session_messages "
                "WHERE session_id = ? ORDER BY seq",
                (session_id,),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def list_sessions(self, user_id: str, limit: int = 50) -> list[dict[str, object]]:
        """用户历史会话列表：标题（首条用户消息）、消息数、最后活跃时间。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id,
                       COUNT(*) AS message_count,
                       MAX(created_at) AS updated_at
                FROM session_messages
                WHERE user_id = ?
                GROUP BY session_id
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        out = []
        for r in rows:
            first = conn.execute(
                "SELECT content FROM session_messages "
                "WHERE session_id = ? AND role = 'user' ORDER BY seq LIMIT 1",
                (r["session_id"],),
            ).fetchone()
            title = (first["content"] if first else "").strip().replace("\n", " ")[:24]
            out.append({
                "session_id": r["session_id"],
                "title": title or "（新对话）",
                "message_count": int(r["message_count"]),
                "updated_at": r["updated_at"],
            })
        return out

    def clear_session_messages(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM session_messages WHERE session_id = ?",
                (session_id,),
            )

    # ---- 教学会话状态（一对一教学闭环） ----

    def get_teaching_state(self, session_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM teaching_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "topic_ids": json.loads(row["topic_ids"]),
            "stage": row["stage"],
            "depth": row["depth"],
            "consecutive_correct": row["consecutive_correct"],
            "consecutive_incorrect": row["consecutive_incorrect"],
            "quiz_history": json.loads(row["quiz_history"]),
            "quiz_correct": json.loads(row["quiz_correct"] or "[]"),
            "last_quiz": json.loads(row["last_quiz_json"]) if row["last_quiz_json"] else None,
            "reteach_question_id": row["reteach_question_id"] if "reteach_question_id" in row.keys() else None,
            "reteach_question": json.loads(row["reteach_question_json"]) if ("reteach_question_json" in row.keys() and row["reteach_question_json"]) else None,
            "last_outcome": row["last_outcome"] if "last_outcome" in row.keys() else None,
            "topic_finished": bool(row["topic_finished"]) if "topic_finished" in row.keys() else False,
            "updated_at": row["updated_at"],
        }

    def save_teaching_state(self, session_id: str, user_id: str, state: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO teaching_sessions
                (session_id, user_id, topic_ids, stage, depth,
                 consecutive_correct, consecutive_incorrect,
                 quiz_history, quiz_correct, last_quiz_json,
                 reteach_question_id, reteach_question_json, last_outcome, topic_finished, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    json.dumps(state.get("topic_ids") or [], ensure_ascii=False),
                    state.get("stage") or "goal_setting",
                    state.get("depth") or "intro",
                    int(state.get("consecutive_correct") or 0),
                    int(state.get("consecutive_incorrect") or 0),
                    json.dumps(state.get("quiz_history") or [], ensure_ascii=False),
                    json.dumps(state.get("quiz_correct") or [], ensure_ascii=False),
                    json.dumps(state["last_quiz"], ensure_ascii=False)
                    if state.get("last_quiz") else None,
                    state.get("reteach_question_id") or None,
                    json.dumps(state.get("reteach_question") or None, ensure_ascii=False)
                    if state.get("reteach_question") else None,
                    state.get("last_outcome") or None,
                    int(bool(state.get("topic_finished"))),
                    _now_iso(),
                ),
            )

    def delete_teaching_state(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM teaching_sessions WHERE session_id = ?",
                (session_id,),
            )

    # ---- 会话摘要（上下文管理 T7） ----

    def get_session_summary(self, session_id: str) -> dict | None:
        """返回 {summary, message_count}；无摘要返回 None。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary, message_count FROM session_summaries "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {"summary": row["summary"], "message_count": int(row["message_count"])}

    def save_session_summary(
        self,
        session_id: str,
        user_id: str,
        summary: str,
        message_count: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session_summaries "
                "(session_id, user_id, summary, message_count, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    summary,
                    int(message_count),
                    _now_iso(),
                ),
            )

    def delete_session_summary(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM session_summaries WHERE session_id = ?",
                (session_id,),
            )

    # ---- 消息交互日志（T15 / D-8：供画像偏好提取与审计） ----
    def append_interaction_log(
        self,
        *,
        user_id: str,
        task_id: str,
        message_id: str,
        from_agent: str,
        to_agents: list[str] | None = None,
        action: str,
        content_summary: str = "",
    ) -> int:
        from datetime import datetime, timezone

        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO interaction_logs "
                "(user_id, task_id, message_id, from_agent, to_agents, action, content_summary, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    task_id,
                    message_id,
                    from_agent,
                    json.dumps(to_agents or [], ensure_ascii=False),
                    action,
                    (content_summary or "")[:300],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return int(cur.lastrowid)

    def list_interaction_logs(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT log_id, task_id, message_id, from_agent, to_agents, action, "
                "content_summary, created_at FROM interaction_logs "
                "WHERE user_id = ? ORDER BY log_id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [
            {
                "log_id": r["log_id"],
                "task_id": r["task_id"],
                "message_id": r["message_id"],
                "from_agent": r["from_agent"],
                "to_agents": json.loads(r["to_agents"]),
                "action": r["action"],
                "content_summary": r["content_summary"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ---- 技能树点亮（v2：管家按进度主动点亮，无积分/手动激活） ----

    def save_skill_activation(
        self,
        activation_id: str,
        user_id: str,
        node_id: str,
        reason: str = "",
        source: str = "concierge",
    ) -> None:
        from datetime import datetime, timezone

        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO skill_activations "
                "(activation_id, user_id, node_id, reason, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    activation_id,
                    user_id,
                    node_id,
                    (reason or "")[:120],
                    source,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    # ── 错题本 ──

    def save_wrong_answer(
        self,
        user_id: str,
        question_id: str,
        knowledge_point_id: str,
        skill_title: str,
        prompt: str,
        options: list[str],
        user_answer: str,
        correct_answer: str,
        explanation: str,
        difficulty: str,
        source: str,
    ) -> None:
        """记录一道错题（同一题重复做错则累加 wrong_count，更新最近错误选项/时间）。"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT wrong_count FROM wrong_answers WHERE user_id=? AND question_id=?",
                (user_id, question_id),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO wrong_answers (user_id, question_id, knowledge_point_id, skill_title,"
                    " prompt, options_json, user_answer, correct_answer, explanation, difficulty, source,"
                    " wrong_count, last_wrong_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)",
                    (user_id, question_id, knowledge_point_id, skill_title, prompt,
                     json.dumps(options, ensure_ascii=False), user_answer, correct_answer,
                     explanation, difficulty, source, now),
                )
            else:
                conn.execute(
                    "UPDATE wrong_answers SET wrong_count=wrong_count+1, user_answer=?, last_wrong_at=?"
                    " WHERE user_id=? AND question_id=?",
                    (user_answer, now, user_id, question_id),
                )

    def update_wrong_reteach_note(
        self, user_id: str, question_id: str, note: str
    ) -> None:
        """把本轮降维解释沉淀到错题记录（供「易错题·降维解释」资源展示）。"""
        with self._connect() as conn:
            conn.execute(
                "UPDATE wrong_answers SET reteach_note=? WHERE user_id=? AND question_id=?",
                (note or "", user_id, question_id),
            )

    def list_wrong_answers(
        self, user_id: str, limit: int = 100, question_id: str | None = None,
    ) -> list[dict[str, object]]:
        """错题列表（按最近做错时间倒序）。"""
        with self._connect() as conn:
            if question_id:
                rows = conn.execute(
                    "SELECT * FROM wrong_answers WHERE user_id=? AND question_id=? ORDER BY last_wrong_at DESC",
                    (user_id, question_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM wrong_answers WHERE user_id=? ORDER BY last_wrong_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["options"] = json.loads(d.pop("options_json") or "[]")
            except (TypeError, ValueError):
                d["options"] = []
            out.append(d)
        return out

    def wrong_answer_stats(self, user_id: str) -> dict[str, object]:
        """错题统计：总数 + 按技能点聚合（用于反馈/薄弱点）。"""
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM wrong_answers WHERE user_id=?", (user_id,),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT skill_title, COUNT(*) c, SUM(wrong_count) wc FROM wrong_answers"
                " WHERE user_id=? GROUP BY skill_title ORDER BY wc DESC, c DESC LIMIT 20",
                (user_id,),
            ).fetchall()
        return {
            "total": total,
            "by_skill": [
                {"skill_title": r[0], "question_count": r[1], "wrong_count": r[2]} for r in rows
            ],
        }

    def delete_wrong_answer(self, user_id: str, question_id: str) -> bool:
        """移除一道错题（掌握后清除）。"""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM wrong_answers WHERE user_id=? AND question_id=?",
                (user_id, question_id),
            )
        return cur.rowcount > 0

    # ---- 掌握度评估（客观由答题实时算；主观/沙盒/画像写这里） ----

    def save_mastery_assessment(
        self, user_id: str, node_id: str, kind: str, score: float, note: str = "",
    ) -> None:
        """写入一次评估（同 user+node+kind 只保留最新一次）。"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM mastery_assessments WHERE user_id=? AND node_id=? AND kind=?"
                , (user_id, node_id, kind),
            )
            conn.execute(
                "INSERT INTO mastery_assessments (user_id, node_id, kind, score, note, created_at) VALUES (?,?,?,?,?,?)",
                (user_id, node_id, kind, float(score), note or "", now),
            )

    def get_mastery_assessments(
        self, user_id: str, node_id: str | None = None,
    ) -> list[dict[str, object]]:
        with self._connect() as conn:
            if node_id:
                rows = conn.execute(
                    "SELECT node_id, kind, score, note, created_at FROM mastery_assessments"
                     " WHERE user_id=? AND node_id=? ORDER BY created_at DESC",
                    (user_id, node_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT node_id, kind, score, note, created_at FROM mastery_assessments"
                     " WHERE user_id=? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
        return [dict(r) for r in rows]


    # ---- 初试引导/先验画像/学习路径（M1） ----

    def clear_mastery_kind(self, user_id: str, kind: str) -> None:
        """清除某用户的某类评估（如重做初试画像时先清 baseline）。"""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM mastery_assessments WHERE user_id=? AND kind=?", (user_id, kind),
            )

    def save_onboarding_profile(
        self, user_id: str, persona: dict, answers: dict, group_status: dict,
        insight: dict | None = None,
    ) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO onboarding_profiles"
                " (user_id, persona_json, identity_answers_json, group_status_json, insight_json, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (user_id,
                 json.dumps(persona, ensure_ascii=False),
                 json.dumps(answers, ensure_ascii=False),
                 json.dumps(group_status, ensure_ascii=False),
                 json.dumps(insight or {}, ensure_ascii=False),
                 now, now),
            )

    def get_onboarding_profile(self, user_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT persona_json, identity_answers_json, group_status_json, insight_json, created_at, updated_at"
                " FROM onboarding_profiles WHERE user_id=?", (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "persona": json.loads(row["persona_json"]),
            "identity_answers": json.loads(row["identity_answers_json"]),
            "group_status": json.loads(row["group_status_json"]),
            "insight": json.loads(row["insight_json"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def next_learning_path_version(self, user_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS v FROM learning_paths WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return int(row["v"]) if row else 1

    def save_learning_path(self, user_id: str, route: dict, status: str = "active") -> int:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        version = self.next_learning_path_version(user_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO learning_paths (user_id, version, route_json, status, note, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (user_id, version, json.dumps(route, ensure_ascii=False), status,
                 route.get("note") or "", now),
            )
        return version

    def get_latest_learning_path(self, user_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT version, route_json, status, note, created_at FROM learning_paths"
                " WHERE user_id=? ORDER BY created_at DESC, version DESC LIMIT 1", (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {"version": int(row["version"]),
                "route": json.loads(row["route_json"]),
                "status": row["status"], "note": row["note"], "created_at": row["created_at"]}

    def list_learning_paths(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version, route_json, status, note, created_at FROM learning_paths"
                " WHERE user_id=? ORDER BY created_at DESC, version DESC", (user_id,),
            ).fetchall()
        return [{"version": int(r["version"]), "route": json.loads(r["route_json"]),
                 "status": r["status"], "note": r["note"], "created_at": r["created_at"]} for r in rows]

    def next_profile_snapshot_version(self, user_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS v FROM profile_snapshots WHERE user_id=?", (user_id,),
            ).fetchone()
        return int(row["v"]) if row else 1

    def save_profile_snapshot(self, user_id: str, persona: dict, source: str = "refresh") -> int:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        version = self.next_profile_snapshot_version(user_id)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO profile_snapshots (user_id, version, persona_json, source, created_at)"
                " VALUES (?,?,?,?,?)",
                (user_id, version, json.dumps(persona, ensure_ascii=False), source, now),
            )
        return version

    def get_onboarding_qa(self, user_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT step, answers_json, updated_at FROM onboarding_qa WHERE user_id=?", (user_id,),
            ).fetchone()
        if row is None:
            return {"user_id": user_id, "step": 0, "answers": {}, "updated_at": None}
        return {"user_id": user_id, "step": int(row["step"]), "answers": json.loads(row["answers_json"] or "{}"), "updated_at": row["updated_at"]}

    def save_onboarding_qa(self, user_id: str, step: int, answers: dict) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO onboarding_qa (user_id, step, answers_json, updated_at) VALUES (?,?,?,?)",
                (user_id, int(step), json.dumps(answers or {}, ensure_ascii=False), now),
            )

    def list_profile_snapshots(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version, persona_json, source, created_at FROM profile_snapshots"
                " WHERE user_id=? ORDER BY created_at DESC, version DESC", (user_id,),
            ).fetchall()
        return [{"version": int(r["version"]), "persona": json.loads(r["persona_json"]),
                 "source": r["source"], "created_at": r["created_at"]} for r in rows]

    def list_skill_activations(self, user_id: str) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT node_id, reason, source, created_at FROM skill_activations "
                "WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [
            {
                "node_id": r["node_id"],
                "reason": r["reason"],
                "source": r["source"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ---- 用户长期记忆 ----

    def save_memory(
        self,
        memory_id: str,
        user_id: str,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        source_session: str | None = None,
    ) -> None:
        from datetime import datetime, timezone

        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_memories "
                "(memory_id, user_id, memory_type, content, importance, source_session, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    memory_id,
                    user_id,
                    memory_type,
                    content,
                    importance,
                    source_session,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get_memories(self, user_id: str, limit: int | None = None) -> list[dict[str, object]]:
        with self._connect() as conn:
            sql = (
                "SELECT memory_id, memory_type, content, importance, source_session, created_at "
                "FROM user_memories WHERE user_id = ? ORDER BY importance DESC, created_at DESC"
            )
            params: list[object] = [user_id]
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "memory_id": r["memory_id"],
                "memory_type": r["memory_type"],
                "content": r["content"],
                "importance": r["importance"],
                "source_session": r["source_session"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def delete_memory(self, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM user_memories WHERE memory_id = ?",
                (memory_id,),
            )

    # ---- 文件资产 ----

    def save_asset(self, asset: Asset) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO assets "
                "(asset_id, user_id, session_id, title, asset_type, content, source_tool, evidence_ids_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    asset.asset_id,
                    asset.user_id,
                    asset.session_id,
                    asset.title,
                    asset.asset_type.value,
                    asset.content,
                    asset.source_tool,
                    json.dumps(asset.evidence_ids or [], ensure_ascii=False),
                    asset.created_at,
                ),
            )

    def get_assets(
        self,
        user_id: str,
        asset_type: AssetType | str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        with self._connect() as conn:
            sql = (
                "SELECT asset_id, user_id, session_id, title, asset_type, content, "
                "source_tool, evidence_ids_json, created_at FROM assets WHERE user_id = ?"
            )
            params: list[object] = [user_id]
            if asset_type is not None:
                sql += " AND asset_type = ?"
                params.append(asset_type.value if isinstance(asset_type, AssetType) else asset_type)
            sql += " ORDER BY created_at DESC"
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "asset_id": r["asset_id"],
                "user_id": r["user_id"],
                "session_id": r["session_id"],
                "title": r["title"],
                "asset_type": r["asset_type"],
                "content": r["content"],
                "source_tool": r["source_tool"],
                "evidence_ids": json.loads(r["evidence_ids_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_asset(self, asset_id: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT asset_id, user_id, session_id, title, asset_type, content, "
                "source_tool, evidence_ids_json, created_at FROM assets WHERE asset_id = ?",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "asset_id": row["asset_id"],
            "user_id": row["user_id"],
            "session_id": row["session_id"],
            "title": row["title"],
            "asset_type": row["asset_type"],
            "content": row["content"],
            "source_tool": row["source_tool"],
            "evidence_ids": json.loads(row["evidence_ids_json"]),
            "created_at": row["created_at"],
        }

    def delete_asset(self, asset_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM assets WHERE asset_id = ?",
                (asset_id,),
            )
            return cur.rowcount > 0

    # ---- 对话式沙盒会话 ----

    def save_sandbox_session(self, session: dict) -> None:
        """整行 upsert 沙盒会话。session 需含全部字段（服务层组装好再存）。"""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sandbox_sessions "
                "(session_id, user_id, mode, template_id, customer_json, state_json, "
                " status, score, dims_json, feedback_json, created_at, ended_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session["session_id"],
                    session["user_id"],
                    session["mode"],
                    session["template_id"],
                    json.dumps(session.get("customer") or {}, ensure_ascii=False),
                    json.dumps(session.get("state") or {}, ensure_ascii=False),
                    session.get("status", "active"),
                    session.get("score"),
                    json.dumps(session.get("dims") or [], ensure_ascii=False)
                    if session.get("dims") is not None else None,
                    json.dumps(session.get("feedback") or {}, ensure_ascii=False)
                    if session.get("feedback") is not None else None,
                    session.get("created_at"),
                    session.get("ended_at"),
                ),
            )

    def get_sandbox_session(self, session_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_id, user_id, mode, template_id, customer_json, state_json, "
                "status, score, dims_json, feedback_json, created_at, ended_at "
                "FROM sandbox_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "mode": row["mode"],
            "template_id": row["template_id"],
            "customer": json.loads(row["customer_json"] or "{}"),
            "state": json.loads(row["state_json"] or "{}"),
            "status": row["status"],
            "score": row["score"],
            "dims": json.loads(row["dims_json"]) if row["dims_json"] else None,
            "feedback": json.loads(row["feedback_json"]) if row["feedback_json"] else None,
            "created_at": row["created_at"],
            "ended_at": row["ended_at"],
        }

    def list_sandbox_records(
        self,
        user_id: str,
        limit: int | None = None,
    ) -> list[dict]:
        """已结束沙盒场次（用于成绩统计）。按结束时间倒序。"""
        with self._connect() as conn:
            sql = (
                "SELECT session_id, user_id, mode, template_id, customer_json, state_json, "
                "status, score, dims_json, feedback_json, created_at, ended_at "
                "FROM sandbox_sessions WHERE user_id = ? AND status = 'ended' "
                "ORDER BY ended_at DESC"
            )
            params: list[object] = [user_id]
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        return [self._sandbox_row_to_dict(r) for r in rows]

    @staticmethod
    def _sandbox_row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "mode": row["mode"],
            "template_id": row["template_id"],
            "customer": json.loads(row["customer_json"] or "{}"),
            "state": json.loads(row["state_json"] or "{}"),
            "status": row["status"],
            "score": row["score"],
            "dims": json.loads(row["dims_json"]) if row["dims_json"] else None,
            "feedback": json.loads(row["feedback_json"]) if row["feedback_json"] else None,
            "created_at": row["created_at"],
            "ended_at": row["ended_at"],
        }

    # ---- 数据合规（导出 / 删除，差距项 T7） ----

    def export_user_data(self, user_id: str, plugin_id: str) -> dict[str, object]:
        """打包用户全部数据：画像 / 记忆 / 掌握度 / 答题 / 资产 / 会话消息。"""
        sessions = self._session_ids_for_user(user_id)
        messages: list[dict[str, object]] = []
        for session_id in sessions:
            messages.extend(self.get_session_messages(session_id))
        profile = self.get_learner_profile(user_id)
        return {
            "user_id": user_id,
            "profile": profile.model_dump(mode="json") if profile is not None else None,
            "memories": self.get_memories(user_id),
            "progress_records": [
                r.model_dump(mode="json") for r in self.get_progress_records(user_id, plugin_id)
            ],
            "submissions": [
                s.model_dump(mode="json") for s in self.get_submissions(user_id)
            ],
            "assets": self.get_assets(user_id),
            "session_messages": messages,
            "exported_at": _now_iso(),
        }

    def delete_user_data(self, user_id: str, plugin_id: str) -> None:
        """删除该用户全部个人数据（撤回授权入口）。"""
        with self._connect() as conn:
            # 先取该用户的任务，按外键顺序删除（messages/agent_runs 引用 tasks）
            task_ids = [
                row["task_id"]
                for row in conn.execute(
                    "SELECT task_id FROM tasks WHERE user_id = ?", (user_id,)
                ).fetchall()
            ]
            for task_id in task_ids:
                conn.execute("DELETE FROM agent_runs WHERE task_id = ?", (task_id,))
                conn.execute("DELETE FROM messages WHERE task_id = ?", (task_id,))
            for task_id in task_ids:
                conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM learner_profiles WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_memories WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM progress_records WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM submissions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM assets WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM session_messages WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM sandbox_sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM teaching_sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM session_summaries WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM interaction_logs WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM skill_activations WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM mastery_assessments WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM wrong_answers WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM onboarding_profiles WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM profile_snapshots WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM learning_paths WHERE user_id = ?", (user_id,))
            try:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            except Exception:
                pass

    def _session_ids_for_user(self, user_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT session_id FROM session_messages WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [r["session_id"] for r in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _agent_run_from_row(self, row: sqlite3.Row) -> AgentRun:
        return AgentRun(
            run_id=row["run_id"],
            task_id=row["task_id"],
            agent_id=AgentId(row["agent_id"]),
            status=RunStatus(row["status"]),
            input_message_ids=json.loads(row["input_message_ids_json"]),
            output_message_id=row["output_message_id"],
            attempts=row["attempts"],
            error=row["error"],
        )











