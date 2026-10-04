"""T3 真实验证：四组 baseline 对比实验（D-24，自评口径）。

同一批测试输入 × 四套方案：
  ① 单模型直接生成          — 无检索、无智能体（体现幻觉率与个性化不足）
  ② RAG + 单模型            — 知识库检索 + 单模型生成（无智能体分工）
  ③ 三智能体（管家+检索+生成）— 检索 + 文本生成 Agent（无质量审查）
  ④ 本方案（全量六帽审查）    — 检索 + 生成 + 六顶思考帽交叉验证

对比指标（自评口径）：
  - 证据支撑率（生成片段↔知识库证据映射，幻觉率 = 1 - 支撑率 的代理）
  - 理想要点命中率（该讲的都讲了）
  - 平均时延
  - 审查环节（④独有：幻觉防控机制）

用法：.venv/Scripts/python scripts/run_baseline_compare.py
"""
from __future__ import annotations

import re
import sys
import time
from difflib import SequenceMatcher

ROOT = Path = __import__("pathlib").Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient, LLMResponse
from brain_of_cloud.plugins.tour_guide import TourGuidePlugin
from brain_of_cloud.services.agents.black_hat import BlackHatAgent
from brain_of_cloud.services.agents.blue_hat import BlueHatAgent
from brain_of_cloud.services.agents.green_hat import GreenHatAgent
from brain_of_cloud.services.agents.red_hat import RedHatAgent
from brain_of_cloud.services.agents.text_generator import TextGeneratorAgent
from brain_of_cloud.services.agents.white_hat import WhiteHatAgent
from brain_of_cloud.services.agents.yellow_hat import YellowHatAgent

# 测试输入（6 题，覆盖讲解/法规/流程/文化类）
QUESTIONS = [
    ("园林构景", "请为导游资格证考生生成一份《中国古典园林的构景手法》学习材料", ["借景", "对景", "框景", "漏景", "抑景"]),
    ("格式条款", "请生成一份旅游合同中「格式条款」考点讲解材料", ["格式条款", "提示", "说明", "免责", "责任"]),
    ("接站流程", "请生成一份导游接站服务实操指南", ["航班", "核对", "举牌", "行李", "清点"]),
    ("导游证", "请生成导游人员管理条例中「导游证分级」的考点总结", ["初级", "中级", "高级", "特级", "考试"]),
    ("跨文化", "请生成接待外国游客时的跨文化沟通要点", ["禁忌", "宗教", "礼仪", "习惯", "文化"]),
    ("投诉处理", "请生成旅游投诉处理办法考点材料", ["投诉", "受理", "时效", "处理", "机构"]),
]


def longest_lcs(a: str, b: str) -> int:
    return max((m.size for m in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()), default=0)


def split_fragments(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n+|。|；", text) if len(p.strip()) >= 15]
    return parts[:30]


def support_ratio(fragments: list[str], evidence_texts: list[str], keywords: list[str]) -> float:
    """片段中被知识库证据支撑（LCS≥15 或含目标关键词）的比例。"""
    if not fragments:
        return 0.0
    supported = 0
    for f in fragments:
        if any(longest_lcs(f, ev) >= 15 for ev in evidence_texts):
            supported += 1
            continue
        if any(k in f for k in keywords):
            supported += 1
    return supported / len(fragments)


def baseline_single(llm: LLMClient, q: str) -> tuple[str, float]:
    t0 = time.time()
    for _ in range(2):  # 空返回重试一次（LLM 偶发）
        resp: LLMResponse = llm.chat(
            [{"role": "user", "content": q + "\n请直接输出学习材料正文。"}],
            max_tokens=1500,
            temperature=0.7,
        )
        if (resp.content or "").strip():
            break
    return resp.content or "", time.time() - t0


def baseline_rag(llm: LLMClient, plugin, q: str, kws: list[str]) -> tuple[str, float, list[str]]:
    t0 = time.time()
    evs = plugin.search(q, top_k=5)
    ev_texts = [e.content for e in evs]
    prompt = (
        f"参考以下知识库证据生成学习材料（可用自己的话讲解，不得编造）：\n"
        + "\n".join(f"- {t[:300]}" for t in ev_texts)
        + f"\n\n任务：{q}\n请直接输出材料正文。"
    )
    for _ in range(2):  # 空返回重试一次
        resp: LLMResponse = llm.chat([{"role": "user", "content": prompt}], max_tokens=1500, temperature=0.7)
        if (resp.content or "").strip():
            break
    return resp.content or "", time.time() - t0, ev_texts


def baseline_three_agents(llm: LLMClient, plugin, q: str) -> tuple[str, float, list[str]]:
    """检索 + 文本生成 Agent（无审查）。"""
    from brain_of_cloud.domain.models import AgentId, Evidence, Message
    from brain_of_cloud.services.agents.retrieval import RetrievalResult
    t0 = time.time()
    evs = plugin.search(q, top_k=5)
    ev_texts = [e.content for e in evs]
    evidence = [
        Evidence(chunk_id=e.chunk_id, content=e.content, source=e.source, trust_score=e.trust_score,
                 knowledge_point_ids=list(e.knowledge_point_ids or []))
        for e in evs
    ]
    agent = TextGeneratorAgent(llm)
    msg = Message(message_id="m", task_id="t", from_agent=AgentId.TEXT_GENERATOR, content=q, lsn=1)
    content = agent.run(msg, RetrievalResult(evidence=evidence, query=q))
    return content or "", time.time() - t0, ev_texts


def full_six_hats(llm: LLMClient, plugin, q: str) -> tuple[str, float, list[str], str]:
    """④ 本方案：检索 + 生成 + 五帽审查 + 蓝帽综合。"""
    from brain_of_cloud.domain.models import AgentId, Evidence, Message
    from brain_of_cloud.services.agents.retrieval import RetrievalResult
    t0 = time.time()
    evs = plugin.search(q, top_k=5)
    ev_texts = [e.content for e in evs]
    evidence = [
        Evidence(chunk_id=e.chunk_id, content=e.content, source=e.source, trust_score=e.trust_score,
                 knowledge_point_ids=list(e.knowledge_point_ids or []))
        for e in evs
    ]
    agent = TextGeneratorAgent(llm)
    msg = Message(message_id="m", task_id="t", from_agent=AgentId.TEXT_GENERATOR, content=q, lsn=1)
    content = agent.run(msg, RetrievalResult(evidence=evidence, query=q)) or ""
    # 五帽并行审查 + 蓝帽综合
    white, black = WhiteHatAgent(llm), BlackHatAgent(llm)
    green, yellow, red = GreenHatAgent(llm), YellowHatAgent(llm), RedHatAgent(llm)
    rw = white.run(content, evidence)
    rb = black.run(content, evidence)
    rg = green.run(content, evidence)
    ry = yellow.run(content, evidence)
    rr = red.run(content, evidence)
    blue = BlueHatAgent(llm)
    verdict = blue.coordinate(content, {
        AgentId.WHITE_HAT: rw,
        AgentId.BLACK_HAT: rb,
        AgentId.GREEN_HAT: rg,
        AgentId.YELLOW_HAT: ry,
        AgentId.RED_HAT: rr,
    })
    return content, time.time() - t0, ev_texts, verdict


def main() -> int:
    print("=== T3 四组 baseline 对比（真实 API，自评口径）===")
    llm = LLMClient()
    plugin = TourGuidePlugin()
    rows = []
    for tag, q, kws in QUESTIONS:
        print(f"\n── {tag}")
        row = {"q": tag}
        # ① 单模型
        c1, t1 = baseline_single(llm, q)
        f1 = split_fragments(c1)
        row["single"] = {"t": round(t1, 1), "frags": len(f1),
                         "support": round(support_ratio(f1, [], kws), 2)}
        # ② RAG
        c2, t2, ev2 = baseline_rag(llm, plugin, q, kws)
        f2 = split_fragments(c2)
        row["rag"] = {"t": round(t2, 1), "frags": len(f2),
                      "support": round(support_ratio(f2, ev2, kws), 2)}
        # ③ 三智能体
        c3, t3, ev3 = baseline_three_agents(llm, plugin, q)
        f3 = split_fragments(c3)
        row["three"] = {"t": round(t3, 1), "frags": len(f3),
                        "support": round(support_ratio(f3, ev3, kws), 2)}
        # ④ 全量六帽
        c4, t4, ev4, verdict4 = full_six_hats(llm, plugin, q)
        f4 = split_fragments(c4)
        row["full"] = {"t": round(t4, 1), "frags": len(f4),
                       "support": round(support_ratio(f4, ev4, kws), 2),
                       "verdict": verdict4[:30]}
        rows.append(row)
        print(f"  ① {row['single']} | ② {row['rag']} | ③ {row['three']} | ④ {row['full']}")

    # 汇总
    print("\n=== 汇总（平均值，自评口径）===")
    keys = ["single", "rag", "three", "full"]
    for k in keys:
        ts = [r[k]["t"] for r in rows]
        ss = [r[k]["support"] for r in rows]
        print(f"  {k:6s} 平均时延 {sum(ts)/len(ts):5.1f}s | 证据支撑率 {sum(ss)/len(ss)*100:5.1f}%")
    full_verdicts = [r["full"]["verdict"] for r in rows]
    passed = sum(1 for v in full_verdicts if "合格" in v)
    print(f"  ④ 审查判定：{passed}/{len(full_verdicts)} 份材料一次通过六帽审查")

    out = ROOT / "docs" / "eval" / "baseline-compare.json"
    import json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows, "note": "自评口径：证据支撑率为幻觉率代理指标"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
