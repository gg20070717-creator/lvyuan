from __future__ import annotations

import inspect
import json
from typing import Any, Callable

from brain_of_cloud.tools.types import ToolCall, ToolDef, ToolResult


class ToolRegistry:
    """Maps tool names to their definitions and handler functions."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}
        self._handlers: dict[str, Callable[..., str]] = {}

    def register(self, tool: ToolDef, handler: Callable[..., str]) -> None:
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return all tool defs in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def execute(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.name)
        if handler is None:
            content = json.dumps({"error": f"unknown tool: {call.name}"}, ensure_ascii=False)
        else:
            try:
                # 参数鲁棒性（T16 实战发现）：LLM 偶发传入多余/类型不符参数 →
                # 只传 handler 签名接受的键，避免 TypeError 使整个工具调用失败
                sig = inspect.signature(handler)
                allowed = {
                    k: v for k, v in (call.arguments or {}).items()
                    if k in sig.parameters
                }
                content = handler(**allowed)
            except Exception as exc:
                content = json.dumps({"error": str(exc)}, ensure_ascii=False)
        return ToolResult(id=call.id, name=call.name, content=content)

    def has(self, name: str) -> bool:
        return name in self._tools
