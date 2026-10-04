"""沙盒 v2 真实验证：完整模拟情景的模拟器（真实 DeepSeek API）。
验证点：
  A. 对话不再固定轮数：同一阶段自然展开多轮（>2 轮后才可能推进）
  B. 游客心理状态随对话演变：信任度变化、情绪波动（模拟角色连续反应）
  C. 剧情推进由目标达成驱动：advanced 达成才推进，未达成不强制
  D. 隐藏诉求随信任流露
  E. 完整跑通一局：多阶段 → 场景完成 → 评估落库
用法：.venv/Scripts/python scripts/verify_sandbox_v2.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brain_of_cloud.llm.client import LLMClient
from brain_of_cloud.services.sandbox import SandboxService
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
    print("=== 沙盒 v2 完整情景模拟器真实验证 ===")
    tmp = tempfile.mkdtemp(prefix="boc_sb2_")
    store = SQLiteStore(Path(tmp) / "sb.sqlite")
    store.initialize()
    svc = SandboxService(llm_client=LLMClient(), store=store)

    # ── 场景：江南古镇 · 游客违规（3 阶段） ──
    print("\n── 开局 ──")
    session = svc.start_session(user_id="u_sb2", template_id="t_guzhen_violation")
    sid = session["session_id"]
    print(f"  游客：{session['customer']['name']}（{session['customer']['nationality']}）")
    print(f"  开场白：{session['messages'][0]['content'][:60]}")
    print(f"  初始信任：{session['customer_state']['trust']}")

    # 模拟一位实习导游的表现（先好、后失误、再补救）
    guide_lines = [
        "先生您好！这里是文物保护区域，基座是不能踩踏的，请您先移步护栏外，我来为您介绍这里的历史。",
        "实在抱歉刚才语气有点急。这里有一千多年的历史了，保护它是为了留给更多人看，您看那边有个拍照点，角度特别好。",
        "我给您安排了前排的位置，等下讲解的时候您站我旁边，还能优先提问。",
        "如果您对这段历史感兴趣，行程结束我可以给您整理一份云冈石窟的讲解资料。",
        "咱们继续往前走，前面还有更精彩的内容等着您。",
    ]
    stage_turns_log: list[int] = []
    trust_log: list[int] = []
    mood_log: list[str] = []
    revealed = False
    last = None
    max_rounds = 12
    for i, line in enumerate(guide_lines):
        if i >= max_rounds:
            break
        last = svc.send_message(sid, line)
        stage_turns_log.append(last["stage"])
        trust_log.append(last["trust"])
        mood_log.append(last["mood"])
        if last["hidden_revealed"]:
            revealed = True
        print(f"  轮{i+1} [阶段{last['stage']} 信任{last['trust']} 心情{last['mood']}] 游客：{last['reply'][:44]}")
        if last["scene_complete"]:
            break

    # A. 最少展开轮数语义：阶段 1（min_turns=2）必须展开 ≥2 轮；总轮数 > 3
    stage1_turns = len([s for s in stage_turns_log if s == 1])
    check("A 阶段1（min_turns=2）展开 ≥2 轮", stage1_turns >= 2, f"→ 阶段轨迹 {stage_turns_log}")
    check("A 总对话轮数 > 3（完整情景展开）", len(stage_turns_log) >= 4, f"→ {len(stage_turns_log)} 轮")

    # B. 心理状态演变：信任度有变化
    check("B 信任度随对话演变", len(set(trust_log)) >= 2, f"→ 轨迹 {trust_log}")
    # D. 隐藏诉求流露（若已发生）
    check("D 隐藏诉求随信任流露", revealed, "（本局未流露则不算失败，属自然剧情）")

    # E. 场景完成
    if last and last["scene_complete"]:
        print("  场景已完成！")
        check("E 场景完成", True)
    else:
        print("  场景未完成（对话轮数限制）——补几轮完成它")
        tail = [
            "您看，前面这座桥的工艺非常特别，我给您讲讲。",
            "谢谢您今天的配合，我送您到下一个集合点。",
            "期待您明天的行程，有任何需要随时找我。",
        ]
        for line in tail:
            last = svc.send_message(sid, line)
            print(f"  轮[{last['stage']} 信任{last['trust']}] 游客：{last['reply'][:44]}")
            if last["scene_complete"]:
                break
        check("E 场景完成", bool(last and last["scene_complete"]))

    # 评估落库
    print("\n── 结算评估 ──")
    ended = svc.end_session(sid, user_id="u_sb2")
    check("E 评估完成并落库", ended["status"] == "ended" and ended["score"] is not None, f"→ 得分 {ended.get('score')}")
    print(f"  得分：{ended['score']} | 五维：{ended['dims']}")
    print(f"  亮点：{ended['feedback']['strengths'][:2]}")
    print(f"  建议：{ended['feedback']['suggestions'][:2]}")
    check("E 报告资产已生成", any(a.get("asset_type") == "report" for a in svc._store.get_assets("u_sb2")), "")

    # ── F. 失误局：糟糕的导游 → 游客情绪下降、信任崩塌、压力事件 ──
    print("\n── F. 失误局：糟糕的服务话术 → 情绪与信任反应 ──")
    session2 = svc.start_session(user_id="u_sb2", template_id="t_guzhen_violation")
    sid2 = session2["session_id"]
    bad_lines = [
        "这是景区规定，你踩了就是你的问题，赶紧出来。",
        "别问我，规定就是这样，我管不了那么多。",
        "拍照点？没空安排，你们自己看着办吧。",
        "投诉？随你便，反正不是我负责。",
    ]
    trust2: list[int] = []
    mood2: list[str] = []
    tension_hit = False
    for line in bad_lines:
        r = svc.send_message(sid2, line)
        trust2.append(r["trust"])
        mood2.append(r["mood"])
        if r["tension"]:
            tension_hit = True
        print(f"  轮[{r['stage']} 信任{r['trust']} 心情{r['mood']}] 游客：{r['reply'][:44]}")
        if r["tension"]:
            print(f"    → 压力事件触发！{r['stage_tip']['message'][:50]}")
            break
    check("F 糟糕服务 → 信任下降", trust2[-1] < trust2[0], f"→ 轨迹 {trust2}")
    check("F 情绪恶化", set(mood2) & {"不满", "愤怒"} != set(), f"→ {mood2}")
    check("F 压力事件触发（投诉/威胁）", tension_hit, "（话术足够差时会触发）")

    print(f"\n=== 结果: {PASS} 通过 / {FAIL} 失败 ===")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
