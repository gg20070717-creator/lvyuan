"""景区讲解评分：要点覆盖（本地）+ 环境 LLM 对照景区知识打分出报告。

- 覆盖评分：字符 bigram 模糊匹配，容忍语音识别误差
- AI 打分：把「场景景区知识 + 当前热点（720云 预留）+ 学员转写稿」喂给环境 LLM，
  要求对照知识库事实评分，输出 JSON 报告
- 降级：LLM 不可用时返回规则评分，不中断流程
"""

from __future__ import annotations

from typing import Any

from brain_of_cloud.llm.client import LLMClient

_REPORT_SYSTEM = """你是导游资格证实训的评分专家，擅长对照景区知识点评学员的现场讲解。

输入包含：场景信息、景区知识（评分依据）、学员讲解转写稿、讲解要点覆盖情况。
要求严格对照【景区知识】判断学员讲得对不对、全不全，不要捏造知识。

输出 JSON 对象（只输出 JSON）：
{
  "total_score": 0-100 的整数,
  "coverage": {"covered": ["已覆盖的要点"], "missed": ["遗漏或讲错的要点"]},
  "strengths": ["亮点，2-3 条，引用学员原话"],
  "weaknesses": ["不足，2-3 条，对照知识指出讲错/漏讲之处"],
  "suggestions": ["可执行的改进建议，2-3 条"],
  "summary": "一句话总评（30 字以内）"
}"""


def _parse_report_json(text: str) -> dict:
    """容错解析 LLM 返回的 JSON（容忍 ``` 围栏 / 截断补全）。"""
    import json
    import re

    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start = t.find("{")
        end = t.rfind("}")
        if start == -1 or end <= start:
            raise
        candidate = t[start : end + 1]
        for fix in ("}", "]}", "}]}"):
            try:
                return json.loads(candidate + fix)
            except json.JSONDecodeError:
                continue
        raise


def _norm(s: str) -> str:
    return "".join(str(s).split())


def _bigrams(s: str) -> set[str]:
    return {s[i : i + 2] for i in range(len(s) - 1)}


def point_covered(point: str, transcript: str, threshold: float = 0.45) -> bool:
    p, t = _norm(point), _norm(transcript)
    if not p:
        return False
    if p in t:
        return True
    pb = _bigrams(p)
    if not pb:
        return p in t
    hit = sum(1 for b in pb if b in t)
    return hit / len(pb) >= threshold


def coverage_result(points: list[str], transcript: str) -> dict:
    covered = [p for p in points if point_covered(p, transcript)]
    missed = [p for p in points if p not in covered]
    return {
        "total": len(points),
        "covered": covered,
        "missed": missed,
        "coverage_score": round(len(covered) / len(points) * 100) if points else 0,
    }


def _rule_report(cov: dict, reason: str) -> dict:
    return {
        "total_score": cov["coverage_score"],
        "coverage": cov,
        "strengths": ["覆盖了部分讲解要点"],
        "weaknesses": [f"AI 点评服务暂不可用（{reason}）"],
        "suggestions": ["检查 DEEPSEEK_API_KEY / LLM_BASE_URL 配置后重试"],
        "summary": "已按要点覆盖给出基础评分",
    }


def evaluate_scene(
    scene: dict,
    transcript: str,
    *,
    hotspot_id: str | None = None,
    llm_client: LLMClient | None = None,
) -> dict:
    points = list(scene.get("points") or [])
    cov = coverage_result(points, transcript or "")

    # 当前场景/热点上下文（720云 全景热点预留：AI 打分时知道学员现在在哪）
    hotspot_text = ""
    if hotspot_id:
        for hs in scene.get("hotspots") or []:
            if hs.get("id") == hotspot_id:
                hotspot_text = (
                    f"\n学员当前处于全景热点【{hs.get('name', hotspot_id)}】，"
                    f"应重点讲解：{hs.get('point', '')}"
                )
                break

    knowledge_text = "\n".join(f"- {k}" for k in scene.get("knowledge") or [])
    user = (
        f"场景：{scene.get('title', '')}（{scene.get('location', '')}）\n"
        f"讲解要点：\n" + "\n".join(f"- {p}" for p in points) + "\n\n"
        f"景区知识（评分依据）：\n{knowledge_text or '（暂无）'}\n"
        f"{hotspot_text}\n\n"
        f"学员讲解转写稿：\n{transcript or '（无内容）'}\n\n"
        f"要点覆盖：{len(cov['covered'])}/{cov['total']}；"
        f"已覆盖 {cov['covered']}；遗漏 {cov['missed']}\n\n"
        f"请输出评价报告 JSON。"
    )

    report: dict[str, Any] | None = None
    last_exc: Exception | None = None
    client = llm_client or LLMClient()
    for attempt in (0, 1):
        try:
            resp = client.generate(
                _REPORT_SYSTEM,
                user,
                temperature=0.4 if attempt == 0 else 0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            report = _parse_report_json(resp.content or "{}")
            break
        except Exception as exc:  # noqa: BLE001 —— 解析失败/网络错误，重试一次
            last_exc = exc
            report = None
    if report is None:
        report = _rule_report(cov, str(last_exc))

    report.setdefault("total_score", cov["coverage_score"])
    report.setdefault("coverage", cov)
    report.setdefault("strengths", [])
    report.setdefault("weaknesses", [])
    report.setdefault("suggestions", [])
    report.setdefault("summary", "")

    # 报告跳转学习所需信息（新知识库就绪后填充 knowledge_point_ids）
    report["learn"] = {
        "keyword": scene.get("title", "").split("·")[0].strip(),
        "knowledge_point_ids": list(scene.get("knowledge_point_ids") or []),
    }
    return report
