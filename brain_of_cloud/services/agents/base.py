from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from brain_of_cloud.domain.models import AgentConfig, AgentId
from brain_of_cloud.llm.client import LLMClient


@dataclass(frozen=True)
class AgentResult:
    content: str
    passed: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    agent_id: AgentId

    def __init__(
        self,
        llm_client: LLMClient,
        config: AgentConfig | None = None,
    ) -> None:
        self._llm = llm_client
        self._config = config or AgentConfig(
            agent_id=self.agent_id,
            role_group="unconfigured",
        )

    @property
    def config(self) -> AgentConfig:
        return self._config

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        ...

    def _call_llm(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        temp = temperature if temperature is not None else self._config.temperature
        mt = max_tokens if max_tokens is not None else self._config.max_tokens
        last_error: Exception | None = None
        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._llm.chat(
                    [{"role": "user", "content": user}],
                    system=system,
                    temperature=temp,
                    max_tokens=mt,
                    reasoning_effort=self._config.reasoning_effort,
                    response_format=response_format,
                )
                return response.content
            except Exception as exc:
                last_error = exc
                if attempt == self._config.max_retries:
                    raise last_error

    def _call_llm_json(self, system: str, user: str, **kwargs: Any) -> dict[str, Any]:
        text = self._call_llm(
            system=system,
            user=user,
            response_format={"type": "json_object"},
            **kwargs,
        )
        return json.loads(text)
