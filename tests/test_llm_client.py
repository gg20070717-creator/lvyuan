from unittest.mock import MagicMock, patch

import pytest

from brain_of_cloud.llm.client import LLMClient, LLMResponse


class TestLLMClientConstruction:
    def test_creates_with_explicit_api_key(self):
        client = LLMClient(api_key="sk-test-key")
        assert client._api_key == "sk-test-key"
        assert client.model == "deepseek-chat"

    def test_reads_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key")
        client = LLMClient()
        assert client._api_key == "sk-env-key"

    def test_env_key_overrides_default(self, monkeypatch):
        # 环境变量优先于内置默认 key（无论是否配置了默认值）
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env-key")
        client = LLMClient()
        assert client._api_key == "sk-env-key"

    def test_accepts_custom_model(self):
        client = LLMClient(api_key="sk-test", model="deepseek-v4-flash")
        assert client.model == "deepseek-v4-flash"


class TestLLMClientChat:
    def test_returns_llm_response(self):
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(content="Hello!", reasoning_content=None),
                finish_reason="stop",
            )
        ]
        mock_completion.usage = MagicMock(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )

        with patch("brain_of_cloud.llm.client.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_completion
            )
            client = LLMClient(api_key="sk-test")
            response = client.chat([{"role": "user", "content": "Hi"}])

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello!"
        assert response.finish_reason == "stop"
        assert response.usage_tokens == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    def test_passes_system_message(self):
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(content="ok", reasoning_content=None),
                finish_reason="stop",
            )
        ]
        mock_completion.usage = None

        with patch("brain_of_cloud.llm.client.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_completion
            )
            client = LLMClient(api_key="sk-test")
            client.chat(
                [{"role": "user", "content": "hello"}],
                system="You are helpful.",
            )

            call_kwargs = mock_openai.return_value.chat.completions.create.call_args[1]
            messages = call_kwargs["messages"]
            assert messages[0] == {"role": "system", "content": "You are helpful."}
            assert messages[1] == {"role": "user", "content": "hello"}

    def test_passes_reasoning_effort(self):
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(content="thoughtful", reasoning_content=None),
                finish_reason="stop",
            )
        ]
        mock_completion.usage = None

        with patch("brain_of_cloud.llm.client.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_completion
            )
            client = LLMClient(api_key="sk-test")
            client.chat(
                [{"role": "user", "content": "think"}],
                reasoning_effort=80,
            )

            call_kwargs = mock_openai.return_value.chat.completions.create.call_args[1]
            assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}

    def test_passes_json_response_format(self):
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(content='{"key":"val"}', reasoning_content=None),
                finish_reason="stop",
            )
        ]
        mock_completion.usage = None

        with patch("brain_of_cloud.llm.client.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_completion
            )
            client = LLMClient(api_key="sk-test")
            client.chat(
                [{"role": "user", "content": "json"}],
                response_format={"type": "json_object"},
            )

            call_kwargs = mock_openai.return_value.chat.completions.create.call_args[1]
            assert call_kwargs["response_format"] == {"type": "json_object"}


class TestLLMClientGenerate:
    def test_convenience_method_wraps_chat(self):
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(
                message=MagicMock(content="generated", reasoning_content=None),
                finish_reason="stop",
            )
        ]
        mock_completion.usage = None

        with patch("brain_of_cloud.llm.client.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_completion
            )
            client = LLMClient(api_key="sk-test")
            response = client.generate(
                system="You are a tutor.",
                user="Explain quantum computing.",
            )

        assert response.content == "generated"
        call_kwargs = mock_openai.return_value.chat.completions.create.call_args[1]
        assert call_kwargs["messages"][0] == {
            "role": "system",
            "content": "You are a tutor.",
        }
