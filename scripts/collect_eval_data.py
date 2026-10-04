"""T1+T2 数据采集：测试方案支撑 + 三组差异化画像测试用例包（提交物）。

- 3 组画像 × 4 类任务 = 12 个真实任务（真实 LLM + 全链路多智能体）
- 每个任务记录：输入画像特征 → 协同中间数据（工具链）→ 生成资源 → 引用证据
- 材料按段落切分为「生成片段」，逐条映射知识库证据（自评留痕，幻觉率/覆盖率的计算基础）
- 输出到 `docs/eval/test-cases/`（作为赛题 DR-5 测试数据包提交物）

用法：.venv/Scripts/python scripts/collect_eval_data.py
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

OUT_DIR = ROOT / "docs" / "eval" / "test-cases"

# 三组差异化学习者画像（赛题要求 ≥2 组，这里给 3 组）
PROFILES = [
    {
        "id": "A_student",
        "name": "A 类·旅游专业学生",
        "background": "旅游管理专业大二学生，学过《旅游学概论》，理论尚可，几乎没有带团实操经验，目标一次性通过导游资格证笔试。",
        "level": "basic",
        "style": "理论优先，喜欢先理解再刷题",
        "tasks": [
            "给我讲讲中国古典园林的构景手法",
            "我懂了，出几道题巩固一下",
            "帮我生成一份《政策与法律法规》的考点总结讲义",
        ],
    },
    {
        "id": "B_switch",
        "name": "B 类·国内游导游转型",
        "background": "做了三年国内游导游，带团流程很熟，但外语差、跨文化沟通经验少，想转做入境游地陪，需要补外语话术和文化禁忌。",
        "level": "advanced",
        "style": "实操优先，要话术和场景模拟",
        "tasks": [
            "给我讲讲接待外国游客的跨文化沟通要点",
            "出几道入境游服务的题考考我",
            "帮我生成一份接站服务的实操指南",
        ],
    },
    {
        "id": "C_language",
        "name": "C 类·外语强文旅弱",
        "background": "英语专业毕业，口语流利，但对导游业务完全零基础，法规、景区知识、服务流程都需要从头学，目标考证后兼职做外语导游。",
        "level": "intro",
        "style": "喜欢对比记忆，需要大白话解释",
        "tasks": [
            "给我讲讲导游人员管理条例里导游证怎么分级",
            "出几道基础题让我摸摸底",
            "帮我生成一份《导游业务》的入门学习计划",
        ],
    },
]


def extract_paragraphs(text: str, min_len: int = 20) -> list[str]:
    """材料 → 生成片段（按段落切分，过滤太短的）。"""
    parts = [p.strip() for p in text.replace("\r", "").split("\n\n")]
    out = []
    for p in parts:
        p = p.strip()
        if len(p) >= min_len:
            out.append(p[:200])
    return out


def main() -> int:
    print("=== T1+T2 测试数据采集（真实 API）===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    llm = LLMClient()
    all_cases: list[dict] = []
    stats = {"tasks": 0, "fragments": 0, "failures": 0}

    for profile in PROFILES:
        for t_idx, task in enumerate(profile["tasks"]):
            case_id = f"{profile['id']}_t{t_idx + 1}"
            print(f"\n── {case_id}：{task[:30]}…")
            tmp = tempfile.mkdtemp(prefix="boc_eval_")
            store = SQLiteStore(Path(tmp) / "e.sqlite")
            store.initialize()
            orch = Orchestrator(store=store, plugin=TourGuidePlugin(), llm_client=llm)
            # 捕获管家真实检索到的证据（自评判定依据，避免二次检索错位）
            evidence_pool: list[dict] = []
            _orig_exec = orch._tools.execute
            def _wrap_exec(call):
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
            orch._tools.execute = _wrap_exec
            t0 = time.time()
            try:
                # 注入画像背景（管家据此个性化）
                orch.handle_user_message(profile["id"], case_id, f"先了解下我：{profile['background']}，学习风格：{profile['style']}，当前水平：{profile['level']}")
                r = orch.handle_user_message(profile["id"], case_id, task)
                elapsed = time.time() - t0
                reply = r.response
                # 生成资产（若有）
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
                fragments = extract_paragraphs(reply) + [
                    f"[资产:{a['title']}] {p}" for a in assets
                    for p in extract_paragraphs(a["content"])
                ]
                case = {
                    "case_id": case_id,
                    "profile_id": profile["id"],
                    "profile": {"background": profile["background"], "level": profile["level"], "style": profile["style"]},
                    "task": task,
                    "tool_chain": r.tool_calls_made,          # 协同中间数据：工具调用链
                    "evidence_pool": evidence_pool,           # 管家真实检索到的证据（自评判定依据）
                    "review_verdict": r.review_verdict,
                    "elapsed_s": round(elapsed, 1),
                    "response": reply[:3000],
                    "assets": assets,
                    "fragments": fragments,                    # 自评留痕：生成片段
                    "evidence_ids": [eid for a in assets for eid in a.get("evidence_ids", [])],
                }
                all_cases.append(case)
                stats["tasks"] += 1
                stats["fragments"] += len(fragments)
                print(f"  完成 {elapsed:.0f}s，工具链 {r.tool_calls_made}，片段 {len(fragments)}，回复 {len(reply)} 字")
            except Exception as exc:
                stats["failures"] += 1
                print(f"  [失败] {exc}")
                all_cases.append({
                    "case_id": case_id, "profile_id": profile["id"], "task": task,
                    "error": str(exc)[:200],
                })

    # ── 汇总输出 ──
    manifest = {
        "title": "司南礼客 — 差异化学习者测试数据包（DR-5）",
        "generated_at": datetime.now().isoformat(),
        "engine": "deepseek-v4-flash-vision-exp（真实 API）",
        "profiles": [p["id"] for p in PROFILES],
        "task_count": stats["tasks"],
        "fragment_count": stats["fragments"],
        "cases": [c["case_id"] for c in all_cases],
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in all_cases:
        (OUT_DIR / f"{c['case_id']}.json").write_text(
            json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== 完成: {stats['tasks']} 个任务 / {stats['fragments']} 个生成片段 / {stats['failures']} 个失败 ===")
    print(f"输出目录: {OUT_DIR}")
    return 0 if stats["failures"] == 0 and stats["tasks"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
