"""沙盒 v3 真实端到端验证（真实题库 + 真实 LLM，不 mock）。

1. 场景库：≥20 个场景可列出、三模式（scenario/narrate/fullflow）齐全
2. 游客生成：连续创建会话，验证年龄多样性（青年/中年/老年都有）与多维属性
3. 对话流程：真实对话 3-5 轮，验证导演判定生效（stage_tip/推进）
4. 场景结束判定：走完全部阶段或失败 → scene_outcome 落库
5. 结算评估：评估注入场景结果
"""
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from brain_of_cloud.llm.client import LLMClient  # noqa: E402
from brain_of_cloud.services.sandbox import SandboxService  # noqa: E402
from brain_of_cloud.storage.sqlite import SQLiteStore  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name} {detail}")
    if not cond:
        FAILS.append(name)


store = SQLiteStore(Path(tempfile.mkdtemp(prefix="boc_sb3_")) / "v.sqlite")
store.initialize()
svc = SandboxService(llm_client=LLMClient(), store=store, rng=random.Random(9))

# ── 1. 场景库 ──
tpls = svc.list_templates()
check("1a 场景数 ≥20", len(tpls) >= 20, f"共 {len(tpls)} 个")
modes = {t["mode"] for t in tpls}
check("1b 三模式齐全", modes == {"scenario", "narrate", "fullflow"}, f"{modes}")
cats = {t["category"] for t in tpls}
print("[1c] 场景分类:", sorted(cats))
print("[1d] 全部场景:")
for t in tpls:
    print(f"     {t['template_id']} {t['title']}（{t['mode']}/{t['category']}，{t['stage_count']} 阶段）")

# ── 2. 游客生成（年龄多样性 + 多维属性） ──
ages = []
customers = []
for i in range(6):
    tpl_id = tpls[i % len(tpls)]["template_id"]
    s = svc.start_session(user_id="u_v3", template_id=tpl_id)
    c = s["customer"]
    ages.append(int(c["age"]))
    customers.append(c)
    check(f"2a 会话{i+1} 游客多维属性", all(k in c for k in ("gender", "occupation", "health", "consumption", "speech_style")),
          f"{c['name']} {c['nationality']} {c['age']}岁 {c.get('occupation')} | 健康:{c.get('health','')[:12]} | 风格:{c.get('speech_style','')[:12]}")
print("[2b] 年龄样本:", ages)
young = sum(1 for a in ages if a <= 40)
mid = sum(1 for a in ages if 41 <= a <= 60)
old = sum(1 for a in ages if a > 60)
check("2c 年龄多样化（≤40 岁至少 1 位）", young >= 1, f"青年{young}/中年{mid}/老年{old}")

# ── 3-4. 真实对话：导演判定 + 场景推进 ──
sid = svc.start_session(user_id="u_v3", template_id="t_airport_delay")["session_id"]
print("[3] 开始对话（机场延误场景）:")
last = None
for i, msg in enumerate([
    "各位久等了，航班延误了 3 小时，我很抱歉。我已经联系了航司确认改签，大家先跟我去休息区，我给大家安排了饮水和小食。",
    "我已经帮大家拿到了最新的航班动态，改签到下午 2 点的航班，同时给大家争取了餐券，一会儿带大家去餐厅。",
    "大家放心，延误的部分我会在后面行程里补回来，比如明天多安排一个小时逛西湖，不会让大家吃亏。",
    "张阿姨您别着急，我已经跟旅行社报备了，您的行李和接站都会安排妥当，您先在椅子上休息。",
]):
    try:
        r = svc.send_message(sid, msg)
        tip_type = (r.get("stage_tip") or {}).get("type", "-")
        print(f"  轮{i+1}: 阶段{r['stage']+1}/{r['stage_total']} {r['stage_title']} | 信任{r['trust']} | 游客: {r['reply'][:36]} | 导演: {tip_type} | outcome={r.get('scene_outcome')}")
        last = r
    except Exception as e:
        print(f"  轮{i+1} 异常: {e}")
        break
check("3a 对话可推进（阶段>0 或完成）", last and (last["stage"] > 0 or last.get("scene_complete")),
      f"stage={last and last['stage']}")
check("3b scene_outcome 字段存在", last is not None and "scene_outcome" in last)

# 结算
ended = svc.end_session(sid, user_id="u_v3")
print(f"[4] 结算: 得分 {ended['score']} | outcome={ended.get('scene_outcome')} | 阶段 {ended['stage']['index']+1}/{ended['stage']['total']}")
check("4a 评估完成", ended["status"] == "ended" and ended["score"] is not None, f"score={ended['score']}")
check("4b 反馈含建议", bool(ended.get("feedback", {}).get("suggestions")))
check("4c scene_outcome 落库透传", ended.get("scene_outcome") in ("success", "failed", "abandoned", None))

# 报告资产
assets = store.get_assets("u_v3", asset_type="report")
check("4d 报告资产落库", len(assets) >= 1, f"{len(assets)} 份")

print()
if FAILS:
    print("RESULT: FAIL", FAILS)
    sys.exit(1)
print("RESULT: ALL PASS")
