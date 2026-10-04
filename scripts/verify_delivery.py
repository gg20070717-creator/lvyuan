"""真实验证：生成文件资产时管家回复不得复述文件全文（真实 DeepSeek API）。

用户路径：对管家说「生成一份 X 讲义」→ 管家应生成资产文件并简短交付，
回复中不得出现材料正文（大段复制/逐条列完）。

运行：.venv/Scripts/python scripts/verify_delivery.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain_of_cloud.llm.client import LLMClient  # noqa: E402
from brain_of_cloud.plugins import InboundGuidePlugin  # noqa: E402
from brain_of_cloud.services.orchestrator import Orchestrator  # noqa: E402
from brain_of_cloud.storage.sqlite import SQLiteStore  # noqa: E402

FAILURES = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [OK] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        FAILURES.append(name)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="boc_delivery_"))
    store = SQLiteStore(tmp / "verify.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=LLMClient())

    print("== 场景 1：材料请求 → 生成资产 + 简短交付 ==")
    result = orch.handle_user_message("u_verify", "s_verify", "帮我生成一份「外滩导游讲解要点」讲义，做成文件")
    resp = result.response or ""
    print(f"  回复长度: {len(resp)} 字")
    print(f"  回复预览: {resp[:120]!r}")
    check("回复非空", bool(resp))
    check("回复为简短交付（<600 字）", len(resp) < 600, f"实际 {len(resp)} 字")
    check("回复不含材料正文（无『外滩』要点式长文）", "黄浦江" not in resp or len(resp) < 200, "疑似复述正文")
    check("生成资产入库", bool(result.assets), "assets 为空")
    if result.assets:
        aid = result.assets[0]["asset_id"]
        row = store.get_asset(aid)
        check("资产内容完整入库（>500 字）", row and len((row or {}).get("content") or "") > 500,
              f"内容长度 {(row or {}).get('content') and len(row['content'])}")
        check("回复提及学习中心", "学习中心" in resp)
        check("回复不含审查内部词", not any(w in resp for w in ("六帽", "审查意见", "工具调用", "review")),
              "泄漏内部词")

    print("\n== 场景 2：历史资产可读取（get_asset 返回全文） ==")
    rows = store.get_assets("u_verify")
    check("资产列表可查", len(rows) >= 1)
    if rows:
        full = store.get_asset(rows[0]["asset_id"])
        check("资产全文可读取（供 MD 阅读器渲染）", full and len(full.get("content") or "") > 100)

    if FAILURES:
        print(f"\n[FAIL] {len(FAILURES)} 项失败: {FAILURES}")
        return 1
    print("\n[OK] 生成交付链路验证全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
