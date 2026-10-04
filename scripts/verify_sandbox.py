"""真实环境验证 — 对话式沙盒全链路（真实 DeepSeek API）。

验证核心用户路径：
1. 沙盒模板列表（三模式）
2. 创建会话 → 随机游客人设 + 开场白 + 隐藏诉求不泄露
3. 多轮自由对话 → 游客角色扮演回复 + 阶段连续推进（长场景）
4. 结束评估 → 五维评分 + 亮点/不足/建议 + 关联真实知识库技能点
5. 评估报告落学习中心资产 + 用户沙盒记录
6. narrate / route 两种模式冒烟
7. 边界：未知会话 404、已结束会话再发言 404

前置：后端已在 http://127.0.0.1:8000 启动（真实 API）。运行：
  .venv/Scripts/python scripts/verify_sandbox.py
"""

import uuid

import httpx

BASE = "http://127.0.0.1:8000"
USER = f"user_sandbox_{uuid.uuid4().hex[:8]}"
results = []
passed = 0
failed = 0


def report(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    results.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def get(path, params=None, timeout=60):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.get(BASE + path, params=params)
        r.raise_for_status()
        return r.json()


def post(path, payload, timeout=120):
    with httpx.Client(timeout=timeout, trust_env=False) as c:
        r = c.post(BASE + path, json=payload)
        r.raise_for_status()
        return r.json()


def raw_get(path):
    with httpx.Client(timeout=30, trust_env=False) as c:
        return c.get(BASE + path)


# ── 1. 健康 + 模板列表 ──
try:
    report("健康检查", get("/").get("status") == "ok")
except Exception as e:
    report("健康检查", False, str(e))

try:
    tpl = get("/sandbox/templates")
    templates = tpl["templates"]
    modes = {t["mode"] for t in templates}
    ok = len(templates) >= 7 and modes == {"scenario", "narrate", "fullflow"} and all(t["stage_count"] >= 3 for t in templates)
    report("沙盒模板：三模式 ≥7 个，均多阶段", ok, f"count={len(templates)} modes={sorted(modes)}")
except Exception as e:
    report("沙盒模板", False, str(e))

# ── 2. 创建会话：随机人设 + 开场白 + 隐藏诉求不泄露 ──
sid1 = None
try:
    s = post("/sandbox/sessions", {"user_id": USER, "template_id": "t_guzhen_violation"})
    sid1 = s["session_id"]
    c = s["customer"]
    ok = (
        s["status"] == "active"
        and s["template"]["title"] == "江南古镇 · 游客违规"
        and c["name"] in {"汉斯", "玛丽", "阿伦", "佐藤"}
        and "hidden" not in c
        and s["messages"] and s["messages"][0]["role"] == "customer"
        and s["stage"]["index"] == 0
    )
    report("创建会话：随机游客人设 + 开场白 + 隐藏诉求不泄露",
           ok, f"游客={c['name']} 国籍={c['nationality']} 开场白={s['messages'][0]['content'][:30]}...")
except Exception as e:
    report("创建会话", False, str(e))

# 随机性：两次创建会话 id 不同
try:
    s2 = post("/sandbox/sessions", {"user_id": USER, "template_id": "t_guzhen_violation"})
    report("随机性：会话 id 唯一", s2["session_id"] != sid1, f"{s2['session_id'][:16]} vs {sid1[:16] if sid1 else None}")
except Exception as e:
    report("随机性", False, str(e))

# ── 3. 多轮自由对话 + 阶段推进 ──
try:
    scene_complete = False
    turns = 0
    stage_max = 0
    script = [
        "您好，这里是非吸烟区，也是文物保护区，麻烦您先灭一下烟，我来给您讲讲这里的古建筑。",
        "我理解您可能觉得有点突然，不过保护这些几百年的老建筑是景区的规矩，我带您去前面专门的观景台，那里拍照视野更好。",
        "您看这座马头墙，它不只是好看，当年是用来防火的……您要是感兴趣，我再带您去看看保存最完整的一段古街。",
        "谢谢您的配合！今天先带您把古镇的精华走一遍，有什么想了解的随时问我。",
    ]
    stage_progression = []
    while not scene_complete and turns < len(script):
        r = post(f"/sandbox/sessions/{sid1}/messages", {"user_id": USER, "content": script[turns]})
        assert r["reply"], "游客应有回复"
        stage_progression.append((r["stage"], r["stage_advanced"], r["mood"]))
        stage_max = max(stage_max, r["stage"])
        scene_complete = r["scene_complete"]
        turns += 1
    # 至少要推进到第 2 阶段（index>=1）或完成
    ok = turns >= 1 and stage_max >= 1
    report("多轮对话：游客实时回复 + 阶段连续推进",
           ok, f"{turns}轮 · 阶段轨迹={stage_progression} · complete={scene_complete}")
except Exception as e:
    report("多轮对话", False, str(e))

# ── 4. 结束评估 ──
try:
    ended = post(f"/sandbox/sessions/{sid1}/end", {"user_id": USER})
    dims = ended["dims"] or {}
    fb = ended["feedback"] or {}
    ok = (
        ended["status"] == "ended"
        and 0 <= ended["score"] <= 100
        and set(dims.keys()) == {"表达能力", "控场能力", "文化知识", "服务意识", "互动引导"}
        and all(1 <= v <= 5 for v in dims.values())
        and fb.get("strengths") and fb.get("weaknesses") and fb.get("suggestions")
        and fb.get("recommended_skills")
    )
    report("结束评估：五维评分 + 亮点/不足/建议 + 关联知识库技能点",
           ok, f"总分={ended['score']} dims={dims} 关联技能点={[sk['title'][:12] for sk in fb.get('recommended_skills', [])][:3]}")
except Exception as e:
    report("结束评估", False, str(e))

# 幂等：重复结束返回既有结果
try:
    again = post(f"/sandbox/sessions/{sid1}/end", {"user_id": USER})
    report("结束评估：幂等", again["score"] == ended["score"], f"score={again['score']}")
except Exception as e:
    report("结束评估：幂等", False, str(e))

# 已结束会话再发言 → 404
try:
    with httpx.Client(timeout=30, trust_env=False) as c:
        r = c.post(f"{BASE}/sandbox/sessions/{sid1}/messages", json={"user_id": USER, "content": "还能继续吗？"})
    report("边界：已结束会话再发言 404", r.status_code == 404, f"status={r.status_code}")
except Exception as e:
    report("边界：已结束会话再发言 404", False, str(e))

# 未知会话 404
try:
    with httpx.Client(timeout=30, trust_env=False) as c:
        r = c.get(f"{BASE}/sandbox/sessions/no_such_session")
    report("边界：未知会话 404", r.status_code == 404, f"status={r.status_code}")
except Exception as e:
    report("边界：未知会话 404", False, str(e))

# ── 5. 评估报告落资产 + 沙盒记录 ──
try:
    assets = get(f"/users/{USER}/assets")
    sandbox_reports = [a for a in assets["assets"] if a["asset_type"] == "report" and "沙盒评估" in a["title"]]
    ok = len(sandbox_reports) >= 1 and "五维评分" in sandbox_reports[0]["content"]
    report("评估报告落学习中心资产", ok, f"报告数={len(sandbox_reports)}")
except Exception as e:
    report("评估报告落资产", False, str(e))

try:
    records = get(f"/sandbox/users/{USER}/records")["records"]
    ok = len(records) >= 1 and records[0]["score"] is not None and records[0]["title"] == "江南古镇 · 游客违规"
    report("用户沙盒记录：训练场统计数据源", ok, f"记录数={len(records)} 最新分={records[0]['score'] if records else None}")
except Exception as e:
    report("用户沙盒记录", False, str(e))

# ── 6. narrate / route 冒烟 ──
for tpl_id, expect in [("t_yungang", "云冈石窟 · 第20窟"), ("t_ff_mid_trip", "行中 · 入境落地接待全流程")]:
    try:
        s = post("/sandbox/sessions", {"user_id": USER, "template_id": tpl_id})
        sid = s["session_id"]
        assert s["template"]["title"] == expect
        msg = "请各位看这里，让我为大家细细讲解。" if tpl_id.startswith("t_yungang") else "您好，欢迎来到中国！我是您的定制导游，我们核对一下接机信息好吗？"
        r = post(f"/sandbox/sessions/{sid}/messages", {"user_id": USER, "content": msg})
        assert r["reply"]
        ended = post(f"/sandbox/sessions/{sid}/end", {"user_id": USER})
        assert ended["status"] == "ended" and ended["score"] is not None
        report(f"冒烟：{expect}", True, f"游客={s['customer']['name']} 回复={r['reply'][:20]}... 总分={ended['score']}")
    except Exception as e:
        report(f"冒烟：{expect}", False, str(e))

# ── 7. 知识库技能点真实命中（评估反馈 → /knowledge/search 关联） ──
try:
    skills = ended["feedback"]["recommended_skills"]
    ok = all(sk.get("id") and sk.get("title") and sk.get("content") for sk in skills)
    report("关联技能点含真实知识库内容", ok, f"技能点数={len(skills)}")
except Exception as e:
    report("关联技能点", False, str(e))


print("\n===== 汇总 =====")
for r in results:
    print(r)
print(f"\n通过 {passed} / {passed + failed}")
raise SystemExit(0 if failed == 0 else 1)
