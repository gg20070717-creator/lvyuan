from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDef:
    """Definition of a tool that an agent can call."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters


@dataclass
class ToolCall:
    """A request to call a tool, parsed from LLM response."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool call."""
    id: str
    name: str
    content: str  # JSON string result
