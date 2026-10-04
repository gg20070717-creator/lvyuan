"""T21：日志保留 180 天策略（D-22）— 归档/清理过期数据。

默认保留 180 天（赛题数据合规要求）。清理范围：
- interaction_logs（交互日志）
- agent_runs / messages / tasks（协同过程审计，随任务过期）
- session_messages（会话历史，仅清理超期会话）
- session_summaries（会话摘要，随会话清理）

用法：.venv/Scripts/python scripts/cleanup_logs.py [db_path] [--days 180]
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "brain_of_cloud.db"
    days = 180
    if "--days" in sys.argv:
        try:
            days = int(sys.argv[sys.argv.index("--days") + 1])
        except (ValueError, IndexError):
            pass
    if not db_path.exists():
        print(f"数据库不存在: {db_path}（跳过）")
        return 0

    import sqlite3
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    total = 0
    for table, col in [
        ("interaction_logs", "created_at"),
        ("agent_runs", "created_at"),
        ("messages", "created_at"),
        ("submissions", "created_at"),
    ]:
        try:
            cur = conn.execute(f"DELETE FROM {table} WHERE {col} < ?", (cutoff,))
            total += cur.rowcount
        except sqlite3.OperationalError:
            pass  # 表/列不存在
    # 超期会话历史（会话级清理，含其摘要）
    stale = conn.execute(
        "SELECT DISTINCT session_id FROM session_messages WHERE created_at < ?",
        (cutoff,),
    ).fetchall()
    for row in stale:
        sid = row["session_id"]
        conn.execute("DELETE FROM session_messages WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM session_summaries WHERE session_id = ?", (sid,))
        total += 1
    conn.execute("DELETE FROM session_summaries WHERE updated_at < ?", (cutoff,))
    conn.commit()
    conn.close()
    print(f"清理完成：删除 {total} 条过期记录（保留 {days} 天，截止 {cutoff[:10]}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
