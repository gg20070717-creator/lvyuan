"""景区讲解 · 语音实训模块（独立于沙盒对话模块）。

- asr.py     : faster-whisper 本地语音转写（多语种、离线、热词）
- scenes.py  : 景区讲解场景（含讲解要点/景区知识/预留全景热点）
- evaluate.py: 要点覆盖评分 + 环境 LLM 对照景区知识打分出报告
"""

from .asr import transcribe_audio
from .evaluate import evaluate_scene
from .scenes import get_scene, list_scenes

__all__ = ["transcribe_audio", "evaluate_scene", "get_scene", "list_scenes"]
