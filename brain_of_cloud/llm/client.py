from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class LLMResponse:
    content: str
    reasoning_content: str | None = None
    usage_tokens: dict[str, int] | None = None
    finish_reason: str = "stop"


class LLMClient:
    # API key 优先从环境变量 DEEPSEEK_API_KEY 读取；也可在构造时显式传入。
    # 出于安全考虑不把 key 提交进源码。
    _ENV_KEY = "DEEPSEEK_API_KEY"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> None:
        self._api_key = api_key or os.environ.get(self._ENV_KEY)
        if not self._api_key:
            raise ValueError(
                "DeepSeek API key not found. Set DEEPSEEK_API_KEY environment "
                "variable or pass api_key explicitly."
            )
        self._base_url = base_url
        self._model = model
        self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        reasoning_effort: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        built_messages: list[dict[str, Any]] = []
        if system:
            built_messages.append({"role": "system", "content": system})
        built_messages.extend(messages)

        extra_body: dict[str, Any] = {}
        if reasoning_effort is not None:
            extra_body["thinking"] = {"type": "enabled"}

        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=built_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if extra_body:
            kwargs["extra_body"] = extra_body
        if response_format:
            kwargs["response_format"] = response_format

        completion = self._client.chat.completions.create(**kwargs)

        choice = completion.choices[0]
        message = choice.message
        reasoning = getattr(message, "reasoning_content", None)

        usage = None
        if completion.usage:
            usage = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content or "",
            reasoning_content=reasoning,
            usage_tokens=usage,
            finish_reason=choice.finish_reason or "stop",
        )

    def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        reasoning_effort: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        return self.chat(
            [{"role": "user", "content": user}],
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            response_format=response_format,
        )
