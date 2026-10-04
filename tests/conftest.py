"""pytest 全局配置 — 为测试提供占位 API key（测试不发起真实 LLM 调用）。"""

import os

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-dummy-key")
