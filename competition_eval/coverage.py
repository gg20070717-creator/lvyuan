# -*- coding: utf-8 -*-
"""核心知识点覆盖率 · 可辩护口径 v2（用于 live 讲义生成评测）。

口径说明：
  1) 应讲核心点 = 技能点标题 + 知识库正文「要点句」（按 。；！？ 拆句、
     去重、去标点归一），按序取前 top 条（默认 8）。
  2) 生成文本 = 对样本技能点 live 生成（internal/http）的「完整讲义正文」，
     评分时不截断（截断会系统性低估长句命中）。
  3) 覆盖判定（容忍口语化转述，但要求确实讲到该点）：
       - 要点句归一化后整段出现在生成文本中 → 命中；
       - 或 要点句自身字符 bigram 的「包含率」（有多少要点 bigram 出现在
         生成文本中）≥ threshold（默认 0.45，即“约半数要点文字信息在讲义
         中被讲到了”，容忍换词/插修饰/语序微调；不含率不随文本总长稀释，
         因为分母只取要点自身的 bigram 数）；
       - 若要点句可拆出 ≥2 个长度≥6 的分句（，、；：分隔），且任一完整
         分句归一化后整段出现 → 同样视为命中（该句关键表述已在讲义中出现）。
  4) 覆盖率 = 命中要点数 / 应讲核心点数；主指标取逐样本平均。
"""
from __future__ import annotations

import re

def norm(s: str) -> str:
    """去空白与标点，仅保留信息字符。"""
    return re.sub(r"[\s，。；：！？、（）()【】[]《》〈〉“”‘’\"'…·—\-—_]+", "", str(s or ""))

def bigrams(s: str) -> set[str]:
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else set()

def containment(point: str, text: str) -> float:
    """要点字符 bigram 在文本中的包含率 = |P∩T| / |P|（0~1，不随文本长度稀释）。"""
    pb, tb = bigrams(point), bigrams(text)
    if not pb or not tb:
        return 0.0
    return sum(1 for b in pb if b in tb) / len(pb)

def split_points(content: str, min_len: int = 10) -> list[str]:
    """正文 → 要点句（去重、去标点归一）。"""
    out: list[str] = []
    for piece in re.split(r"[。；！？]+", str(content or "").replace("\n", "")):
        p = norm(piece)
        if len(p) >= min_len and p not in out:
            out.append(p)
    return out

def clauses_of(point: str, min_len: int = 6) -> list[str]:
    """把（已归一的）要点句按分句符拆成子句；子句不足时返回空。"""
    p = norm(point)
    out: list[str] = []
    for piece in re.split(r"[,，、;；:：\s]+", p):
        if len(piece) >= min_len and piece not in out:
            out.append(piece)
    return out if len(out) >= 2 else []

def key_points(skill=None, content: str = "", top: int = 8) -> list[str]:
    """应讲核心点：标题（第 1 条）+ 正文前若干要点句。"""
    title = ""
    if skill is not None:
        title = norm(skill.get("title", "") if isinstance(skill, dict) else getattr(skill, "title", ""))
    points: list[str] = []
    if title:
        points.append(title)
    for p in split_points(content):
        if p != title:
            points.append(p)
        if len(points) >= top:
            break
    if not points and isinstance(skill, dict):
        kws = skill.get("keywords") or []
        points = [norm(str(k)) for k in kws if isinstance(k, str) and len(norm(k)) >= 2][:top]
    return points[:top]


def point_covered(point: str, text: str, threshold: float = 0.45) -> bool:
    """要点是否被生成文本覆盖（口径见模块 docstring）。"""
    np_, nt = norm(point), norm(text)
    if not np_ or not nt:
        return False
    if np_ in nt:
        return True
    # 任一完整子句整段出现 → 该句关键表述已被覆盖
    for cl in clauses_of(np_):
        if cl in nt:
            return True
    return containment(np_, nt) >= threshold


def coverage_points(points: list[str], text: str, threshold: float = 0.45):
    covered = [p for p in points if point_covered(p, text, threshold)]
    return {
        "total": len(points),
        "covered": covered,
        "missed": [p for p in points if p not in covered],
        "rate": round(len(covered) / len(points) * 100, 1) if points else 0.0,
    }
