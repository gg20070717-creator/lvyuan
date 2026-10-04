"""faster-whisper 语音转写封装（本地离线、多语种、热词提示）。

- 模型：ASR_MODEL 环境变量，默认 small（~460MB，CPU int8 快）；可选 base/medium
- 热词：initial_prompt 注入导游专有名词，提升专有名词识别率
- 下载：首次使用自动从 HuggingFace 下载；国内默认走 hf-mirror 镜像并禁用 Xet
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# 国内镜像 + 禁用 Xet（否则 hf-mirror 下载会 401）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

_HOTWORDS = [
    "外滩", "万国建筑群", "武康大楼", "豫园", "东方明珠", "黄浦江",
    "南京路", "陆家嘴", "石库门", "法租界", "海关大楼", "和平饭店",
]

_model: Any | None = None
_model_size: str | None = None


def get_model() -> Any:
    """懒加载 Whisper 模型（首次调用触发下载，约 460MB）。"""
    global _model, _model_size
    size = os.environ.get("ASR_MODEL", "small").strip()
    if _model is None or _model_size != size:
        from faster_whisper import WhisperModel

        _model = WhisperModel(size, device="cpu", compute_type="int8")
        _model_size = size
    return _model


def transcribe_audio(
    audio_path: str | Path,
    *,
    language: str | None = None,
    hotwords: list[str] | None = None,
) -> dict:
    """转写音频，返回 {text, language, duration, speech}。

    speech 为语音表现指标（供评价报告使用）：
      char_count      有效字数（中英数字，去标点）
      speech_duration 实际讲话时长（VAD 分段求和，秒）
      speech_rate     语速（字/分钟，参考 180~260）
      pause_count     明显停顿次数（段间静音 > 1s）
      pause_seconds   停顿总时长（秒）
      max_pause       最长停顿（秒）
    """
    import re

    model = get_model()
    words = hotwords if hotwords is not None else _HOTWORDS
    prompt = "、".join(words) + "。"
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
        beam_size=5,
    )
    segs = [
        {"text": (seg.text or "").strip(), "start": float(seg.start), "end": float(seg.end)}
        for seg in segments
    ]
    text = "".join(s["text"] for s in segs).strip()

    # 有效字数：中英文与数字，去标点/空白
    char_count = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))
    speech_duration = max(0.0, sum(s["end"] - s["start"] for s in segs))

    # 停顿：相邻分段之间的静音间隙
    pauses = []
    for i in range(1, len(segs)):
        gap = segs[i]["start"] - segs[i - 1]["end"]
        if gap > 1.0:
            pauses.append(gap)
    pause_seconds = round(sum(pauses), 2)
    speech_rate = round(char_count / speech_duration * 60) if speech_duration > 0 else 0

    return {
        "text": text,
        "language": info.language,
        "duration": round(float(info.duration), 2),
        "speech": {
            "char_count": char_count,
            "speech_duration": round(speech_duration, 2),
            "speech_rate": speech_rate,
            "pause_count": len(pauses),
            "pause_seconds": pause_seconds,
            "max_pause": round(max(pauses), 2) if pauses else 0.0,
        },
    }
