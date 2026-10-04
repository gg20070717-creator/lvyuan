"""帽子审查全覆盖（所有输出经过审查）测试：生成即自动审查。"""
import json
from unittest.mock import MagicMock

from brain_of_cloud.plugins import InboundGuidePlugin
from brain_of_cloud.services.agents.concierge import AgentResponse
from brain_of_cloud.services.orchestrator import Orchestrator
from brain_of_cloud.storage.sqlite import SQLiteStore


def _orch(tmp_path):
    store = SQLiteStore(tmp_path / "a.sqlite")
    store.initialize()
    llm = MagicMock()
    llm.model = "deepseek-v4-pro"
    orch = Orchestrator(store=store, plugin=InboundGuidePlugin(), llm_client=llm)
    orch._user_id_ctx.set("u1")
    orch._session_id_ctx.set("s1")
    return orch, store


def _stub_generate_tool(orch, tool_name: str, payload: dict):
    """mock 工具执行层：生成类工具返回固定成功结果（绕过真实 LLM 生成）。"""
    from brain_of_cloud.tools import ToolResult
    orig = orch._tools.execute
    def fake_execute(call):
        if call.name == tool_name:
            return ToolResult(id=call.id, name=call.name,
                              content=json.dumps(payload, ensure_ascii=False))
        return orig(call)
    orch._tools.execute = fake_execute


def _material_result():
    return {
        "content": "园林构景讲义内容……", "asset_id": "asset_auto_1",
        "title": "园林构景讲义", "asset_type": "lecture",
    }


def test_generation_triggers_auto_review(tmp_path):
    """管家生成材料但没调 review_material → orchestrator 自动触发六帽审查。"""
    orch, store = _orch(tmp_path)
    _stub_generate_tool(orch, "generate_material", _material_result())
    orch._handle_review_material = MagicMock(return_value=json.dumps(
        {"review": "蓝帽检测：合格", "verdict": "passed", "hats": {}},
        ensure_ascii=False,
    ))
    calls = [
        AgentResponse(text="", tool_calls=[
            {"id": "t1", "name": "generate_material",
             "arguments": {"request": "讲义", "evidence": '{"results": []}'}},
        ]),
        AgentResponse(text="讲义已生成，保存在你的学习中心。"),
    ]
    orch._concierge.think = MagicMock(side_effect=calls)

    result = orch.handle_user_message("u1", "s1", "帮我生成一份讲义")

    assert result.review_verdict == "passed"
    orch._handle_review_material.assert_called_once()
    # 自动审查后向管家注入了「已自动完成六帽审查」的说明
    conv = orch._concierge.think.call_args_list[1].args[0]
    assert any(
        m.get("role") == "system" and "自动完成六帽审查" in m.get("content", "")
        for m in conv
    )


def test_auto_review_skipped_when_concierge_reviewed(tmp_path):
    """管家同一轮已带 review_material → 不触发自动审查（防重复审查）。"""
    orch, store = _orch(tmp_path)
    _stub_generate_tool(orch, "generate_material", _material_result())
    orch._handle_review_material = MagicMock(return_value=json.dumps(
        {"review": "蓝帽检测：合格", "verdict": "passed", "hats": {}},
        ensure_ascii=False,
    ))
    calls = [
        AgentResponse(text="", tool_calls=[
            {"id": "t1", "name": "generate_material",
             "arguments": {"request": "讲义", "evidence": '{"results": []}'}},
            {"id": "t2", "name": "review_material", "arguments": {"content": "讲义内容"}},
        ]),
        AgentResponse(text="讲义已生成。"),
    ]
    orch._concierge.think = MagicMock(side_effect=calls)

    result = orch.handle_user_message("u1", "s1", "帮我生成一份讲义")

    # 同轮已带 review_material → 自动审查不触发；管家自己的审查路径执行
    assert orch._handle_review_material.call_count == 0
    assert "review_material" in result.tool_calls_made


def test_auto_review_needs_revision_triggers_revision_guidance(tmp_path):
    """自动审查判需修改 → 注入修订引导；管家未修订前不允许直接交付。"""
    orch, store = _orch(tmp_path)
    _stub_generate_tool(orch, "generate_plan", {
        "plan": "备考计划内容……", "asset_id": "asset_plan_1",
        "title": "个性化备考计划", "asset_type": "plan",
    })
    orch._handle_review_material = MagicMock(return_value=json.dumps(
        {"review": "蓝帽检测：需修改\n事实准确 3/5", "verdict": "needs_revision", "hats": {}},
        ensure_ascii=False,
    ))
    orch._concierge.think = MagicMock(side_effect=[
        AgentResponse(text="", tool_calls=[
            {"id": "t1", "name": "generate_plan", "arguments": {}},
        ]),
        # 管家想直接交付 → 被修订硬约束拦截
        AgentResponse(text="计划已生成，你看看吧。"),
        # 被引导后调 generate_plan 修订
        AgentResponse(text="", tool_calls=[
            {"id": "t2", "name": "generate_plan", "arguments": {}},
        ]),
        AgentResponse(text="计划已修订完成。"),
    ])

    result = orch.handle_user_message("u1", "s1", "给我一个备考计划")

    # 自动审查被触发
    assert orch._handle_review_material.call_count == 2  # 首轮 + 修订轮各审一次
    # 修订引导注入（管家第 3 次 think 收到「审查未通过，不能直接交付」）
    conv3 = orch._concierge.think.call_args_list[2].args[0]
    assert any(
        m.get("role") == "system" and "不能直接交付" in m.get("content", "")
        for m in conv3
    )
    assert "generate_plan" in result.tool_calls_made


def test_red_hat_receives_teaching_context(tmp_path):
    """红帽收到当前教学主题上下文（上下文适配检查）。"""
    orch, store = _orch(tmp_path)
    orch._teaching.set_topic("s1", "u1", ["kp_welcome"])
    red = MagicMock()
    red.run.return_value.content = "红帽个性适配：通过"
    red.run.return_value.passed = True
    orch._red_hat = red
    # 其他帽子 mock 掉（避免真实 LLM）
    for name in ("_white_hat", "_black_hat", "_green_hat", "_yellow_hat"):
        h = MagicMock()
        h.run.return_value.content = "通过"
        h.run.return_value.passed = True
        setattr(orch, name, h)
    orch._blue_hat.coordinate = MagicMock(return_value="蓝帽检测：合格")

    orch._handle_review_material("欢迎词材料内容")

    red.run.assert_called_once()
    kwargs = red.run.call_args.kwargs
    assert kwargs["teaching_context"] is not None
    assert "kp_welcome" in kwargs["teaching_context"] or "当前教学主题" in kwargs["teaching_context"]
