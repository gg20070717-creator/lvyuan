"""真实验证：语音实训模块（/voice/*）在合并后的可访问性与真实 LLM 评测链路。

- 1. /voice/scenes 返回实景讲解场景列表（≥3）
- 2. /voice/evaluate 用真实 DeepSeek API 对讲解文本打分（要点覆盖 + 报告）
- 3. /voice/transcribe 端点已注册（缺文件 -> 422；真实转写依赖首次模型下载，不在本验证内）

运行：.venv/Scripts/python scripts/verify_voice.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from brain_of_cloud.api.app import create_app  # noqa: E402


def main() -> int:
    failures = []
    app = create_app(db_path=Path("__voice_verify_tmp__.sqlite"))
    client = TestClient(app)

    # 1. 场景列表
    r = client.get("/voice/scenes")
    scenes = r.json().get("scenes", [])
    if r.status_code != 200 or len(scenes) < 3:
        failures.append(f"scenes: status={r.status_code}, count={len(scenes)}")
    else:
        ids = {s["scene_id"] for s in scenes}
        print(f"[1/3] /voice/scenes -> {len(scenes)} 个场景 OK（含 bund_voice: {'bund_voice' in ids}）")

    # 2. 真实 LLM 评测（不 mock）
    r = client.post("/voice/evaluate", json={
        "scene_id": "bund_voice",
        "transcript": "各位游客大家好，我们现在所在的就是外滩。这里被称为万国建筑博览群，"
                      "一边是黄浦江，对岸就是陆家嘴金融区，可以看到东方明珠。"
                      "海关大楼的钟声很有名，和平饭店也是标志性建筑。适合傍晚来这里看浦江夜景。",
    })
    if r.status_code != 200:
        failures.append(f"evaluate: status={r.status_code}, body={r.text[:200]}")
    else:
        data = r.json()
        report = data.get("report", {})
        print(f"[2/3] /voice/evaluate -> total_score={report.get('total_score')}, "
              f"coverage={report.get('coverage', {}).get('coverage_score')}, "
              f"strengths={len(report.get('strengths', []))} 条")
        if report.get("total_score") is None:
            failures.append("evaluate: report 缺 total_score")

    # 3. transcribe 端点注册（缺文件 -> 422，避免触发模型下载）
    r = client.post("/voice/transcribe")
    if r.status_code != 422:
        failures.append(f"transcribe: 期望 422（缺文件），实际 {r.status_code}")
    else:
        print("[3/3] /voice/transcribe 已注册（缺文件 422 OK；真实转写需首次下载模型）")

    Path("__voice_verify_tmp__.sqlite").unlink(missing_ok=True)

    if failures:
        print("\n❌ 失败：")
        for f in failures:
            print("  -", f)
        return 1
    print("\n[OK] 语音实训模块验证 3/3 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
