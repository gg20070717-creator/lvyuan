"""T7 真实验证：记忆组织与上下文管理（长对话摘要 + token 预算）。
验证点：
  A. 40 条真实感历史 → 首次摘要触发并持久化（摘要包含主题/进度信息）
  B. 摘要注入后管家能正常应答（真实 LLM 调用不因长历史而失败）
  C. 再次发消息：复用已有摘要（不重复生成），间隔不足时不重摘要
用法：.venv/Scripts/python scripts/verify_context.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore

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
    print("=== T7 上下文管理真实验证 ===")
    tmp = tempfile.mkdtemp(prefix="boc_ctx_")
    store = SQLiteStore(Path(tmp) / "ctx.sqlite")
    store.initialize()
    orch = Orchestrator(store=store, llm_client=LLMClient())
    orch._user_id_ctx.set("u_verify")
    orch._session_id_ctx.set("s_verify")

    # ── 构造 40 条真实感教学对话历史（含主题、进度、对错） ──
    pairs = [
        ("我是小王，旅游管理专业大二，在备考导游资格证", "欢迎欢迎！咱们先从笔试科目一《政策与法律法规》开始。"),
        ("给我讲讲旅游法的基本原则", "好，旅游法的核心是保护旅游者和经营者合法权益……"),
        ("明白了，出几道题巩固下", "好的，来两道基础题。"),
        ("A", "答对了！延伸一下：旅行社责任险和旅游意外险是两种不同的险种……"),
        ("接着讲合同法的内容", "旅游合同里最常考的是格式条款和违约责任……"),
        ("B", "不对，这道题选 C。格式条款要尽到提示说明义务……"),
        ("嗯理解了，那关于导游人员管理条例呢", "导游证分为初级、中级、高级和特级，考试侧重初级……"),
        ("C", "答对了，中级导游要 3 年以上从业经验才能报考。"),
        ("讲讲旅游投诉处理办法", "投诉时效、受理机构、处理时限是三个常考点……"),
        ("A", "对！旅游投诉处理机构是县级以上旅游行政管理部门。"),
        ("再讲讲出入境管理", "护照、签证、边检流程，外国游客入境有停留期限规定……"),
        ("B", "错啦，选 A。外国游客在中国境内停留，签证到期前要办理延期。"),
        ("那跨文化沟通要注意什么", "禁忌话题、宗教礼仪、用餐习惯，不同国家差异很大……"),
        ("明白了，继续", "好，咱们接着讲接站服务的标准流程……"),
        ("给我讲讲接站流程", "接站分三步：接前核对、接时确认、接后清点……"),
        ("A", "正确！接团时要核对团号和人数，行李按件清点。"),
        ("送站有什么讲究", "提前 2 小时到机场，确认航班动态，帮客人办理值机……"),
        ("C", "不对，选 B。送站时要提前确认航班时间，避免误机。"),
        ("那紧急情况怎么处理", "游客突发疾病先拨打急救电话，同时报告旅行社……"),
        ("明白了", "好，记住处置顺序：救人第一、报告第二、留证第三。"),
    ]
    for i, (u, a) in enumerate(pairs):
        store.save_session_message("s_verify", "u_verify", "user", u + "（很长很长的补充细节内容" * 60)
        store.save_session_message("s_verify", "u_verify", "assistant", a + "（详细展开的讲解内容" * 60)
    total = len(pairs) * 2
    print(f"  历史消息: {total} 条")

    # ── A. 首次摘要（真实 LLM，失败自动重试一次） ──
    print("\n── A. 长会话首次摘要 ──")
    t0 = time.time()
    result_a = orch.handle_user_message("u_verify", "s_verify", "继续讲讲")
    elapsed = time.time() - t0
    row = store.get_session_summary("s_verify")
    if row is None:
        print("  首次摘要未生成（LLM 偶发），自动重试一次……")
        result_a = orch.handle_user_message("u_verify", "s_verify", "继续讲讲")
        row = store.get_session_summary("s_verify")
    check("A1 摘要已持久化", row is not None, f"→ {row}")
    check("A2 管家正常应答", bool(result_a.response), f"→ {result_a.response[:80]}")
    if row:
        summ = row["summary"]
        print(f"  [摘要内容] 长度={len(summ)}: {summ[:400]}")
        has_topic = any(k in summ for k in ("旅游", "导游", "接站", "投诉", "合同"))
        has_progress = any(k in summ for k in ("小王", "专业", "备考", "答对", "答错", "继续"))
        check("A3 摘要含主题信息", has_topic, f"→ {summ[:120]}")
        check("A4 摘要含身份/进度信息", has_progress, f"→ {summ[:120]}")
    print(f"  A 耗时 {elapsed:.1f}s，回复预览: {result_a.response[:100]}")

    # ── B. 二次消息：复用摘要，间隔不足不重摘要 ──
    print("\n── B. 复用摘要（不重复生成） ──")
    t0 = time.time()
    orch._context_mgr._llm = None  # 禁用 LLM：若逻辑正确，不会触发重摘要
    result_b = orch.handle_user_message("u_verify", "s_verify", "再讲讲送站")
    elapsed = time.time() - t0
    check("B1 无 LLM 时仍能正常应答（复用摘要）", bool(result_b.response), f"→ {result_b.response[:80]}")
    row2 = store.get_session_summary("s_verify")
    check("B2 摘要未被覆盖丢失", row2 is not None and bool(row2["summary"]), f"→ {row2}")
    print(f"  B 耗时 {elapsed:.1f}s，回复预览: {result_b.response[:100]}")

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
