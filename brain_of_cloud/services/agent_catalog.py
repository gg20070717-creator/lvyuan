"""可运行协作角色清单，供调用轨迹与前端使用。预留枚举单独说明。"""
from __future__ import annotations

from typing import Callable

AGENTS = [
    {"id": "concierge", "name": "旅鸢管家", "role": "理解目标、选择工具、组织交付", "group": "调度", "icon": "sparkle"},
    {"id": "profile", "name": "学情画像师", "role": "记录经验与学习目标", "group": "学习", "icon": "user"},
    {"id": "retrieval", "name": "知识检索师", "role": "检索知识库与参考依据", "group": "学习", "icon": "search"},
    {"id": "text_generator", "name": "学习材料师", "role": "生成讲义与训练材料", "group": "学习", "icon": "filetext"},
    {"id": "training_analyzer", "name": "测评分析师", "role": "题库抽题、判分、学情分析", "group": "学习", "icon": "bookcheck"},
    {"id": "essay_question", "name": "进阶出题师", "role": "生成简答题与评分要点", "group": "学习", "icon": "target"},
    {"id": "learning_planner", "name": "学习规划师", "role": "根据画像与掌握度安排路线", "group": "学习", "icon": "map"},
    {"id": "white_hat", "name": "白帽 · 事实", "role": "核查事实与证据", "group": "六帽", "icon": "shield"},
    {"id": "black_hat", "name": "黑帽 · 风险", "role": "排查漏洞与风险", "group": "六帽", "icon": "shield"},
    {"id": "green_hat", "name": "绿帽 · 创意", "role": "提出创新与改进", "group": "六帽", "icon": "sparkle"},
    {"id": "yellow_hat", "name": "黄帽 · 价值", "role": "评估价值与可行性", "group": "六帽", "icon": "star"},
    {"id": "red_hat", "name": "红帽 · 适配", "role": "检查学员与主题适配", "group": "六帽", "icon": "user"},
    {"id": "blue_hat", "name": "蓝帽 · 汇总", "role": "汇总五帽结论与修订建议", "group": "六帽", "icon": "check"},
    {"id": "customer_generator", "name": "游客人设师", "role": "生成游客背景与隐藏诉求", "group": "实战", "icon": "user"},
    {"id": "customer_simulator", "name": "模拟游客", "role": "结合情绪与记忆回应学员", "group": "实战", "icon": "msg"},
    {"id": "scene_director", "name": "场景导演", "role": "判断场景推进、达成与失败", "group": "实战", "icon": "map"},
    {"id": "sandbox_evaluator", "name": "实战评估师", "role": "五维评分与复盘建议", "group": "实战", "icon": "trophy"},
]
RESERVED = ["chart_generator", "html_demo_generator", "image_generator"]
ALIASES = {"draft": "text_generator", "trainer": "training_analyzer", "analyzer": "training_analyzer", "essay": "essay_question", "planner": "learning_planner"}


def trace_event(cb: Callable[[dict], None] | None, agent: str, role: str, status: str = "working", detail: str = "", **meta) -> None:
    if cb is None:
        return
    canonical = ALIASES.get(agent, agent)
    info = next((a for a in AGENTS if a["id"] == canonical), None)
    try:
        cb({"agent": canonical, "name": info["name"] if info else ("六帽协作组" if agent == "review" else "实战流程"), "role": role,
            "status": status, "detail": detail[:180], **meta})
    except Exception:
        pass  # 观察回调失败不影响业务执行
