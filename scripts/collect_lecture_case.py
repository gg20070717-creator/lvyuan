"""补跑一个「生成讲义」用例：验证 generate_material 路径的资产携带结构化引用链（evidence_ids）。
输出到 docs/eval/test-cases/（并入 T1 自评与 T2 数据包）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore

OUT = ROOT / "docs" / "eval" / "test-cases" / "A_student_t4.json"


def extract_paragraphs(text: str, min_len: int = 20) -> list[str]:
    parts = [p.strip() for p in text.replace("\r", "").split("\n\n")]
    return [p[:200] for p in parts if len(p.strip()) >= min_len]


def main() -> int:
    print("=== 补跑：A 画像 × 讲义生成（generate_material 路径）===")
    tmp = tempfile.mkdtemp(prefix="boc_lecture_")
    store = SQLiteStore(Path(tmp) / "l.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=TourGuidePlugin(), llm_client=LLMClient())
    # 捕获管家真实检索证据（自评判定依据）
    evidence_pool: list[dict] = []
    _orig_exec = orch._tools.execute
    def _exec_wrapped(call):
        r = _orig_exec(call)
        if call.name == "search_knowledge":
            try:
                data = json.loads(r.content)
                for it in data.get("results", []):
                    evidence_pool.append({
                        "chunk_id": it.get("chunk_id", ""),
                        "content": it.get("content", ""),
                        "source": it.get("source", ""),
                    })
            except Exception:
                pass
        return r
    orch._tools.execute = _exec_wrapped
    profile = "旅游管理专业大二学生，理论尚可、实操零基础，目标导游资格证笔试。"
    t0 = time.time()
    orch.handle_user_message("A_student", "s_lecture", f"先了解下我：{profile}")
    r = orch.handle_user_message(
        "A_student", "s_lecture",
        "帮我生成一份《中国古典园林的构景手法》考点总结讲义，要包含各手法定义和典型例子",
    )
    elapsed = time.time() - t0
    assets = []
    for aid in [a["asset_id"] for a in r.assets]:
        asset = store.get_asset(aid)
        if asset:
            assets.append({
                "asset_id": aid,
                "title": asset["title"],
                "asset_type": asset["asset_type"],
                "content": asset["content"][:3000],
                "evidence_ids": asset.get("evidence_ids", []),
            })
    case = {
        "case_id": "A_student_t4",
        "profile_id": "A_student",
        "profile": {"background": profile, "level": "basic", "style": "理论优先"},
        "task": "帮我生成一份《中国古典园林的构景手法》考点总结讲义",
        "tool_chain": r.tool_calls_made,
        "review_verdict": r.review_verdict,
        "elapsed_s": round(elapsed, 1),
        "response": r.response[:3000],
        "assets": assets,
        "evidence_pool": evidence_pool,
        "fragments": extract_paragraphs(r.response) + [
            f"[资产:{a['title']}] {p}" for a in assets for p in extract_paragraphs(a["content"])
        ],
        "evidence_ids": [eid for a in assets for eid in a.get("evidence_ids", [])],
    }
    OUT.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    # 更新 manifest
    manifest_path = OUT.parent / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["cases"].append("A_student_t4")
        manifest["task_count"] += 1
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"工具链: {r.tool_calls_made} | 审查: {r.review_verdict}")
    print(f"资产: {len(assets)} 个, evidence_ids: {len(case['evidence_ids'])} 条")
    print(f"已保存: {OUT}")
    return 0 if assets and case["evidence_ids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
