"""TaskRunner phase 粒度测试（差距项 T6）。"""
import time

from brain_of_cloud.services.task_runner import TaskRunner


def test_task_phase_reports_progress():
    runner = TaskRunner()
    seen_phases: list[str] = []

    def slow_fn(phase_cb=None):
        if phase_cb:
            phase_cb("working")
            seen_phases.append("working")
        time.sleep(0.05)
        if phase_cb:
            phase_cb("reviewing")
            seen_phases.append("reviewing")
        return "done"

    task_id = runner.submit(
        slow_fn,
        result_builder=lambda outcome: {"content": outcome},
        phase_cb=None,
    )
    # 初始 queued（worker 可能已抢先置 working，两种情况都合法）
    assert runner.get(task_id).phase in ("queued", "working")

    deadline = time.time() + 5
    record = None
    while time.time() < deadline:
        record = runner.get(task_id)
        if record.status in ("completed", "failed"):
            break
        time.sleep(0.02)

    assert record is not None
    assert record.status == "completed"
    assert record.phase == "done"
    assert seen_phases == ["working", "reviewing"]


def test_task_phase_failed_marks_error():
    runner = TaskRunner()

    def boom():
        raise RuntimeError("boom")

    task_id = runner.submit(boom)

    deadline = time.time() + 5
    record = None
    while time.time() < deadline:
        record = runner.get(task_id)
        if record.status in ("completed", "failed"):
            break
        time.sleep(0.02)

    assert record is not None
    assert record.status == "failed"
    assert record.phase == "failed"
    assert "boom" in record.error
