"""历史对话列表与切换 真实验证（真实 API）：
  A. 同一用户两个历史会话 → 列表返回 2 条（标题/消息数/时间）
  B. 切换会话：加载指定会话消息完整（role/content 顺序）
  C. 切回旧会话继续对话 → 消息追加，列表消息数更新
用法：.venv/Scripts/python scripts/verify_sessions.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import httpx
import uvicorn
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def main() -> int:
    print("=== 历史会话列表与切换 真实验证 ===")
    tmp = tempfile.mkdtemp(prefix="boc_hist_")
    db = Path(tmp) / "hist.sqlite"

    # 起后端（随机空闲端口，避免与残留 uvicorn 线程冲突）
    import socket
    from brain_of_cloud.api.app import create_app
    app = create_app(db_path=str(db))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(30):
        try:
            httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            break
        except Exception:
            time.sleep(0.5)
    base = f"http://127.0.0.1:{port}"
    client = httpx.Client(trust_env=False, timeout=300.0)  # 真实 API 对话较慢

    user = "u_hist"

    def send_and_wait(session_id: str, content: str, timeout: float = 300.0) -> dict:
        """发消息并轮询任务完成（异步任务）。"""
        r = client.post(f"{base}/messages", json={"user_id": user, "session_id": session_id, "content": content})
        r.raise_for_status()
        task_id = r.json()["task_id"]
        t0 = time.time()
        while time.time() - t0 < timeout:
            rec = client.get(f"{base}/tasks/{task_id}").json()
            if rec["status"] in ("completed", "failed"):
                return rec
            time.sleep(2)
        return {"status": "timeout"}

    try:
        # ── A. 两个会话真实对话 ──
        print("\n── A. 创建两个历史会话 ──")
        rec_a = send_and_wait("hist_a", "给我讲讲中国古典园林的构景手法")
        print(f"  会话A 首轮：{rec_a['status']}")
        rec_b = send_and_wait("hist_b", "给我制定一份备考计划")
        print(f"  会话B 首轮：{rec_b['status']}")
        check("A 两轮对话任务均完成", rec_a["status"] == "completed" and rec_b["status"] == "completed",
              f"→ {rec_a['status']}/{rec_b['status']}")

        sessions = client.get(f"{base}/sessions", params={"user_id": user}).json()["sessions"]
        print(f"  列表：{[s['session_id'] for s in sessions]}")
        check("A 两个会话均出现在列表", len(sessions) == 2, f"→ {len(sessions)}")
        by_id = {s["session_id"]: s for s in sessions}
        check("A 会话标题取自首条消息", "园林" in by_id.get("hist_a", {}).get("title", ""), f"→ {by_id.get('hist_a', {}).get('title')}")
        check("A 消息数正确（user+assistant ≥2）", by_id.get("hist_a", {}).get("message_count", 0) >= 2,
              f"→ {by_id.get('hist_a', {}).get('message_count')}")

        # ── B. 切换会话：加载历史消息 ──
        print("\n── B. 切换会话加载历史 ──")
        msgs = client.get(f"{base}/sessions/hist_a/messages").json()["messages"]
        roles = [m["role"] for m in msgs]
        print(f"  会话A 消息：{roles}（{len(msgs)} 条）")
        check("B 历史消息完整加载", len(msgs) >= 2 and roles[0] == "user" and "assistant" in roles, f"→ {roles}")
        check("B 首条内容为历史提问", "园林" in msgs[0]["content"], f"→ {msgs[0]['content'][:20]}")

        # ── C. 切回旧会话继续对话 → 消息追加 ──
        print("\n── C. 旧会话继续对话 ──")
        rec_c = send_and_wait("hist_a", "我懂了，出几道题巩固一下")
        print(f"  继续对话：{rec_c['status']}")
        check("C 续聊任务完成", rec_c["status"] == "completed", f"→ {rec_c['status']}")
        sessions2 = client.get(f"{base}/sessions", params={"user_id": user}).json()["sessions"]
        by_id2 = {s["session_id"]: s for s in sessions2}
        check("C 会话A 消息数增长", by_id2["hist_a"]["message_count"] > by_id["hist_a"]["message_count"],
              f"→ {by_id['hist_a']['message_count']} → {by_id2['hist_a']['message_count']}")
        check("C 会话B 未被影响", by_id2["hist_b"]["message_count"] == by_id["hist_b"]["message_count"], "")
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        client.close()

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
