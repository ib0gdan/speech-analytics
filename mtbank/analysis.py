"""Shared analysis core — run_analysis().

Audio in, the task's JSON contract out. Framework-agnostic on purpose: both the OpenWebUI
Pipeline and the FastAPI service import this one function, so the chat path and the REST path
can never drift (CORE-01).

  audio -> fetch/decode -> faster-whisper -> Оператор/Клиент diarization
        -> supervisor fans out 4 agents (classifier, quality, compliance, summarizer) -> merge
"""

from __future__ import annotations

import time
from typing import Any

from .agents.supervisor import run_agents
from .asr.audio import decode_waveform, fetch_audio
from .asr.diarizer import diarize
from .asr.transcriber import transcribe
from .logging_config import get_logger, log_event

logger = get_logger("mtbank.analysis")


def _transcribe(audio_source: str | bytes, filename: str | None, request_id: str) -> list[dict]:
    """Real ASR: fetch -> decode -> whisper -> diarize."""
    path = fetch_audio(audio_source, filename=filename)
    waveform = decode_waveform(path)
    segments = transcribe(path, request_id=request_id)
    return diarize(segments, waveform, request_id=request_id)


def run_analysis(
    audio_source: str | bytes,
    *,
    filename: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Analyze one call recording and return the full contract dict.

    Args:
        audio_source: audio URL, local path, or raw bytes.
        filename: original name (used for the extension when `audio_source` is bytes).
        request_id: correlation id for the JSON logs; generated if omitted.

    Raises:
        AnalysisError: user-facing failure (bad URL, undecodable file, no speech).
    """
    rid = request_id or f"req-{int(time.time() * 1000)}"
    started = time.time()
    src_repr = filename or (audio_source if isinstance(audio_source, str) else "<bytes>")
    log_event(logger, "analysis_start", request_id=rid, audio_source=src_repr)

    transcript = _transcribe(audio_source, filename, rid)
    analysis = run_agents(transcript, request_id=rid)

    result: dict[str, Any] = {
        "transcript": transcript,
        **analysis,
        "request_id": rid,
        "elapsed_s": round(time.time() - started, 2),
    }
    log_event(
        logger, "analysis_done", request_id=rid,
        segments=len(transcript), elapsed_s=result["elapsed_s"],
        topic=result["classification"]["topic"],
    )
    return result
