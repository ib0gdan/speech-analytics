"""faster-whisper transcription (ASR-01, ASR-03, ASR-05).

Model choice is a valve/env (`WHISPER_MODEL`, default `small`, `compute_type=int8`).
Rationale (see README): on a CPU-only host `small int8` transcribes a 5-min call in ~50 s,
staying inside the task's <60 s budget; `medium` overshoots it. The model is loaded lazily
and cached per process so the first request pays the cost, not startup.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from ..errors import AnalysisError, EmptyAudioError
from ..logging_config import get_logger, log_event

logger = get_logger("mtbank.asr.transcriber")

_model: Any = None
_model_key: tuple[str, str] | None = None
_lock = threading.Lock()


def _get_model():
    """Lazily build (and cache) the WhisperModel for the configured valves."""
    global _model, _model_key

    name = os.getenv("WHISPER_MODEL", "small")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    key = (name, compute_type)

    with _lock:
        if _model is None or _model_key != key:
            from faster_whisper import WhisperModel  # heavy: import lazily

            log_event(logger, "whisper_load", model=name, compute_type=compute_type)
            _model = WhisperModel(name, device="cpu", compute_type=compute_type)
            _model_key = key
    return _model


def warmup() -> None:
    """Download and load the model at service startup.

    Otherwise the FIRST user request pays for a ~500 MB download plus model init — on a cold
    container that measured 70 s, blowing the 60 s response budget for whoever happens to be
    first. Called from the Pipeline's on_startup and the API's lifespan.
    """
    _get_model()


def transcribe(path: Path, *, language: str = "ru", request_id: str = "-") -> list[dict]:
    """Return segments: [{start, end, text}, ...] (speaker is assigned by the diarizer)."""
    model = _get_model()
    try:
        segments, info = model.transcribe(
            str(path),
            language=language,
            beam_size=1,               # greedy: fastest, adequate for this task
            vad_filter=True,           # built-in Silero VAD drops silence -> faster + cleaner
            condition_on_previous_text=False,
        )
        out = [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments
            if s.text and s.text.strip()
        ]
    except Exception as e:  # noqa: BLE001
        raise AnalysisError(f"Ошибка распознавания речи: {e}", code="asr_failed") from e

    if not out:
        raise EmptyAudioError()

    log_event(
        logger, "transcribe_done", request_id=request_id,
        segments=len(out), duration_s=round(info.duration, 2), language=info.language,
    )
    return out
