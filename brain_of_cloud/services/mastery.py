"""主客观综合掌握度（技能点级）——给知识技能树“颜色填充/点亮”提供数据。

规则（可配）：
- 六个普通知识域：客观(题库通过率) 80% + 管家主观 20% + 沙盒 0%(占位)
- 入境游实战能力域：客观 40% + 管家主观 10% + 沙盒 50%(接口占位，暂不参与)
- baseline(初试画像直接给分) 预留：一旦存在直接作为掌握度。

客观分：该技能点题库固定题（客观+简答，简答由 AI 判分计入通过）中，
历史答对题数 / 题库题数。沙盒评分后续通过 mastery_assessments(kind=sandbox) 接入。
"""

from __future__ import annotations

from typing import Any

from brain_of_cloud.storage.sqlite import SQLiteStore


class MasteryService:
    # 权重（之后要调按技能点/域配置也容易改）
    WEIGHTS_NORMAL = {"objective": 0.80, "concierge": 0.20, "sandbox": 0.0}
    WEIGHTS_INBOUND = {"objective": 0.40, "concierge": 0.10, "sandbox": 0.50}
    INBOUND_BOOK_TITLES = {"入境游实战能力"}

    def __init__(self, plugin: Any, store: SQLiteStore) -> None:
        self._plugin = plugin
        self._store = store
        self._q_by_kp: dict[str, list] | None = None
        self._correct_ids: set[str] | None = None
        self._correct_user: str | None = None
        self._assess_all: dict[tuple[str, str], float] | None = None
        self._assess_user: str | None = None

    # ---------- 基础数据（带缓存：一次请求只建一次索引 / 查一次答题记录） ----------

    def _ensure(self, user_id: str) -> None:
        if self._q_by_kp is None:
            q_by_kp: dict[str, list] = {}
            try:
                for q in self._plugin.questions():
                    q_by_kp.setdefault(q.knowledge_point_id, []).append(q)
            except Exception:
                q_by_kp = {}
            self._q_by_kp = q_by_kp
        if self._correct_ids is None or self._correct_user != user_id:
            try:
                history = self._store.get_submissions(user_id)
            except Exception:
                history = []
            self._correct_ids = {r.question_id for r in history if r.correct}
            self._correct_user = user_id
        if self._assess_all is None or self._assess_user != user_id:
            try:
                rows = self._store.get_mastery_assessments(user_id)
            except Exception:
                rows = []
            amap: dict[tuple[str, str], float] = {}
            for r in rows:
                amap[(str(r["node_id"]), str(r["kind"]))] = float(r["score"] or 0)
            self._assess_all = amap
            self._assess_user = user_id

    def _correct_question_ids(self, user_id: str) -> set[str]:
        self._ensure(user_id)
        return self._correct_ids or set()

    def _book_title_of(self, kp_id: str) -> str:
        try:
            sk = self._plugin._kb.skills_by_id.get(kp_id)
            return getattr(sk, "book_title", "") or ""
        except Exception:
            return ""

    def _is_inbound(self, kp_id: str) -> bool:
        return self._book_title_of(kp_id) in self.INBOUND_BOOK_TITLES

    def _objective(self, user_id: str, kp_id: str) -> dict[str, float]:
        """客观：答对固定题数 / 题库固定题总数（0~1）。"""
        self._ensure(user_id)
        pool = (self._q_by_kp or {}).get(kp_id, [])
        total = len(pool)
        if total == 0:
            return {"score": 0.0, "done": 0, "total": 0}
        correct = self._correct_question_ids(user_id)
        done = sum(1 for q in pool if q.question_id in correct)
        return {"score": round(done / total, 4), "done": done, "total": total}

    def _assessments(self, user_id: str, kp_id: str) -> dict[str, float]:
        self._ensure(user_id)
        amap = self._assess_all or {}
        out: dict[str, float] = {}
        for k, v in amap.items():
            if k[0] == kp_id:
                out[k[1]] = v
        return out

    # ---------- 综合 ----------

    def skill_mastery(self, user_id: str, kp_id: str) -> dict[str, object]:
        """某技能点综合掌握度（0~100）及分项。"""
        w = self.WEIGHTS_INBOUND if self._is_inbound(kp_id) else self.WEIGHTS_NORMAL
        ass = self._assessments(user_id, kp_id)
        baseline = ass.get("baseline")
        if baseline is not None:
            return {
                "mastery": round(max(0.0, min(100.0, baseline)), 1),
                "objective": 0.0, "concierge": 0.0, "sandbox": 0.0,
                "baseline": baseline, "weights": w, "is_inbound": self._is_inbound(kp_id),
            }
        obj = self._objective(user_id, kp_id)
        concierge = ass.get("concierge", 0.0)
        sandbox = ass.get("sandbox", 0.0)
        total = (
            obj["score"] * 100.0 * w["objective"]
            + concierge * w["concierge"]
            + sandbox * w["sandbox"]
        )
        return {
            "mastery": round(max(0.0, min(100.0, total)), 1),
            "objective": round(obj["score"] * 100.0, 1),
            "objective_done": obj["done"],
            "objective_total": obj["total"],
            "concierge": round(concierge, 1),
            "sandbox": round(sandbox, 1),
            "baseline": baseline,
            "weights": w,
            "is_inbound": self._is_inbound(kp_id),
        }

    def assess(
        self, user_id: str, node_id: str, kind: str, score: float, note: str = "",
    ) -> dict[str, object]:
        """写入一次评估（管家主观 / 沙盒 / 初试画像共用接口）。"""
        if kind not in ("concierge", "sandbox", "baseline"):
            raise ValueError(f"unsupported assessment kind: {kind}")
        s = max(0.0, min(100.0, float(score)))
        self._store.save_mastery_assessment(user_id, node_id, kind, s, note or "")
        return self.skill_mastery(user_id, node_id)
