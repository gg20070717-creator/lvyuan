"""轻量级异步任务执行器 — 长耗时智能体任务在后台线程运行，HTTP 立即返回。

用于解决「生成训练材料 + 六帽审查」这类需要多轮 LLM 调用、耗时数分钟的场景：
前端不再阻塞等待，而是轮询 GET /tasks/{task_id} 获取结果。
"""

from __future__ import annotations

import inspect
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


def _accepts_kw(fn: Callable[..., Any], name: str) -> bool:
    """fn 是否接受名为 name 的关键字参数（无法检查时保守返回 True）。"""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return True
    return any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        or (
            p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            and p.name == name
        )
        for p in sig.parameters.values()
    )


@dataclass
class TaskRecord:
    task_id: str
    status: str = "pending"  # pending / running / completed / failed
    phase: str = "queued"    # queued / working / reviewing / done / failed
    trace: list[dict] = field(default_factory=list)  # 实时多 Agent 工作轨迹（前端直播用）
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None


class TaskRunner:
    def __init__(self, max_tasks: int = 200) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = threading.Lock()
        self._max_tasks = max_tasks

    def submit(
        self,
        fn: Callable[..., Any],
        *,
        result_builder: Callable[[Any], dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        with self._lock:
            # 简单清理：超过上限时丢弃最旧的任务
            if len(self._tasks) >= self._max_tasks:
                oldest = min(
                    self._tasks, key=lambda k: self._tasks[k].created_at
                )
                self._tasks.pop(oldest, None)
            self._tasks[task_id] = TaskRecord(task_id=task_id)

        def worker() -> None:
            with self._lock:
                self._tasks[task_id].status = "running"
            try:
                # 若调用方传了 phase_cb=None 占位，注入绑定 task_id 的上报回调
                effective_kwargs = dict(kwargs)
                # phase_cb / trace_cb 占位→绑定本任务的上报回调（函数不接受则丢弃占位）
                for cb_name in ("phase_cb", "trace_cb"):
                    if cb_name in effective_kwargs and not _accepts_kw(fn, cb_name):
                        effective_kwargs.pop(cb_name, None)
                if "phase_cb" in effective_kwargs:
                    effective_kwargs["phase_cb"] = lambda phase: self.update_phase(task_id, phase)
                if "trace_cb" in effective_kwargs:
                    effective_kwargs["trace_cb"] = lambda event: self.record_trace(task_id, event)
                outcome = fn(**effective_kwargs)
                built = (
                    result_builder(outcome)
                    if result_builder is not None
                    else {"content": str(outcome)}
                )
                with self._lock:
                    record = self._tasks[task_id]
                    record.result = built
                    record.status = "completed"
                    record.phase = "done"
                    record.finished_at = time.time()
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                with self._lock:
                    record = self._tasks[task_id]
                    record.status = "failed"
                    record.phase = "failed"
                    record.error = str(exc)
                    record.finished_at = time.time()

        threading.Thread(target=worker, daemon=True, name=f"task-{task_id}").start()
        return task_id

    def update_phase(self, task_id: str, phase: str) -> None:
        """由后台任务上报当前阶段（queued/working/reviewing/done/failed）。"""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is not None:
                record.phase = phase

    def record_trace(self, task_id: str, event: dict) -> None:
        """后台任务实时上报 Agent 工作轨迹（检索/起草/逐帽审查/交付…），前端轮询可见。"""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is not None:
                ev = dict(event or {})
                ev.setdefault("ts", time.time())
                record.trace.append(ev)

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)
