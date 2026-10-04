"""文件资产服务 — 把系统在对话/工具箱中生成的学习资源落为可管理的文件资产。

资产是「学习中心」的数据来源：讲义、实操指南、备考计划、学习报告等
用户在使用过程中生成的内容都会被保存，供查看 / 导出 / 删除。
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from brain_of_cloud.domain.models import Asset, AssetType
from brain_of_cloud.storage.sqlite import SQLiteStore


class AssetService:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self._store = store

    def create(
        self,
        user_id: str,
        title: str,
        content: str,
        *,
        asset_type: AssetType = AssetType.TEXT,
        session_id: str = "",
        source_tool: str = "",
        evidence_ids: list[str] | None = None,  # 结构化引用链（T14）
    ) -> dict[str, object]:
        if not self._store:
            return {}
        asset = Asset(
            asset_id=f"asset_{uuid4().hex[:12]}",
            user_id=user_id,
            session_id=session_id,
            title=title[:80],
            asset_type=asset_type,
            content=content,
            source_tool=source_tool,
            evidence_ids=evidence_ids or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._store.save_asset(asset)
        return asset.model_dump()

    def list(
        self,
        user_id: str,
        asset_type: AssetType | str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        if not self._store:
            return []
        return self._store.get_assets(user_id, asset_type=asset_type, limit=limit)

    def get(self, asset_id: str) -> dict[str, object] | None:
        if not self._store:
            return None
        return self._store.get_asset(asset_id)

    def delete(self, asset_id: str) -> bool:
        if not self._store:
            return False
        return self._store.delete_asset(asset_id)

    def sync_wrong_book(self, user_id: str, wrong_items: list[dict]) -> dict[str, object] | None:
        """把易错题整理成「每道错题一张卡片」的资产（易错题·降维解释）。

        每道错题生成一个独立文件资产：题干 + 选项 + 你的选择/正确答案
        + 解析 + 对话中沉淀的降维解释。幂等：先清该用户旧的 wrong_book 资产再重建。
        """
        if not self._store:
            return None
        for old in self._store.get_assets(user_id, asset_type=AssetType.WRONG_BOOK):
            try:
                self._store.delete_asset(old["asset_id"])
            except Exception:
                pass
        if not wrong_items:
            return self.create(
                user_id, "易错题·降维解释",
                "# 易错题·降维解释\n\n暂无错题。做错的题目会自动生成每道一卡的降维解释资源。",
                asset_type=AssetType.WRONG_BOOK, source_tool="wrong_book",
            )
        created: dict[str, object] | None = None
        for w in wrong_items:
            prompt = (w.get("prompt") or "").strip() or "（题干缺失）"
            title = prompt if len(prompt) <= 26 else prompt[:26] + "…"
            lines = ["# 易错题·降维解释", "", f"## {prompt}"]
            if w.get("options"):
                lines.append("")
                lines.append("选项：" + " / ".join(str(o) for o in w["options"]))
            lines.append("")
            lines.append(f"- 技能点：{w.get('skill_title') or '未标注'}")
            lines.append(f"- 你的选择：{w.get('user_answer') or ''}")
            lines.append(f"- 正确答案：{w.get('correct_answer') or ''}")
            if w.get("difficulty"):
                lines.append(f"- 难度：{w.get('difficulty')}")
            lines.append(f"- 错误次数：{w.get('wrong_count', 1)}")
            note = (w.get("reteach_note") or "").strip()
            if note:
                lines += ["", "## 降维解释", "", note]
            elif w.get("explanation"):
                lines += ["", "## 解析", "", str(w.get("explanation"))]
            content = "\n".join(lines)
            created = self.create(
                user_id, title, content,
                asset_type=AssetType.WRONG_BOOK, source_tool="wrong_book",
            )
        return created

    def migrate_legacy_wrong_book(self, user_id: str, wrong_items: list[dict]) -> bool:
        """把旧版「一个文件装所有错题」的合集迁移为「每道错题一张卡片」。

        检测到旧的合集资产（标题为「易错题·降维解释」且内容是编号错题列表）时，
        重建为逐题资产。幂等：未检测到旧格式则不动作。"""
        if not self._store:
            return False
        try:
            existing = self._store.get_assets(user_id, asset_type=AssetType.WRONG_BOOK)
        except Exception:
            return False
        legacy = any(
            (a.get("title") == "易错题·降维解释")
            and ("道易错题（按最近做错时间倒序" in (a.get("content") or ""))
            for a in existing
        )
        if not legacy:
            return False
        try:
            self.sync_wrong_book(user_id, wrong_items)
        except Exception:
            pass
        return True

