"""Shared analysis core — run_analysis().

PHASE 1 = SKELETON. Returns the FULL target JSON contract (matching the task README) with
clearly-marked STUB values. The signature and return shape are frozen now so later phases
swap internals without changing any interface:

  - Phase 2 replaces `_transcribe()` with real faster-whisper + Оператор/Клиент diarization.
  - Phase 3 replaces `_analyze()` with the 4 real agents (classifier / quality / compliance / summarizer).
"""

from __future__ import annotations

import time
from typing import Any

from .logging_config import get_logger, log_event

logger = get_logger("mtbank.analysis")


# --- Phase 2 will replace this with real faster-whisper output ---
_STUB_TRANSCRIPT: list[dict[str, Any]] = [
    {"speaker": "Оператор", "start": 0.0, "end": 4.2,
     "text": "Добрый день, МТБанк, меня зовут Анна. Чем могу помочь?"},
    {"speaker": "Клиент", "start": 4.5, "end": 8.1,
     "text": "Здравствуйте, хочу узнать про кредит наличными."},
    {"speaker": "Оператор", "start": 8.3, "end": 13.0,
     "text": "Конечно, подскажу условия. Уточните желаемую сумму и срок."},
]


def _transcribe(audio_source: str | None, request_id: str) -> list[dict[str, Any]]:
    log_event(logger, "transcribe_stub", request_id=request_id,
              audio_source=audio_source, segments=len(_STUB_TRANSCRIPT))
    return _STUB_TRANSCRIPT


def _analyze(transcript: list[dict[str, Any]], request_id: str) -> dict[str, Any]:
    # Phase 3 replaces the hardcoded values below with the 4 agents' real output.
    log_event(logger, "agents_stub", request_id=request_id, transcript_segments=len(transcript))
    return {
        "classification": {"topic": "кредиты", "priority": "medium"},
        "quality_score": {
            "total": 75,
            "checklist": {
                "greeting": True,
                "need_detection": True,
                "solution_provided": False,
                "farewell": False,
            },
        },
        "compliance": {"passed": True, "issues": []},
        "summary": ("ЗАГЛУШКА: клиент обратился по вопросу кредита наличными; "
                    "оператор начал консультацию и запросил сумму и срок."),
        "action_items": ["ЗАГЛУШКА: отправить условия кредита на email клиента"],
    }


def run_analysis(audio_source: str | None = None, *, request_id: str | None = None) -> dict[str, Any]:
    """Analyze one call recording and return the full contract dict.

    Args:
        audio_source: URL or filename of the audio (not yet downloaded in Phase 1).
        request_id: correlation id for logs; generated if omitted.
    """
    rid = request_id or f"req-{int(time.time() * 1000)}"
    log_event(logger, "analysis_start", request_id=rid, audio_source=audio_source)

    transcript = _transcribe(audio_source, rid)
    analysis = _analyze(transcript, rid)

    result: dict[str, Any] = {
        "transcript": transcript,
        **analysis,
        "request_id": rid,
        "stub": True,  # Phase 1 marker — removed once ASR + agents are real
    }
    log_event(logger, "analysis_done", request_id=rid,
              topic=result["classification"]["topic"],
              quality_total=result["quality_score"]["total"])
    return result
