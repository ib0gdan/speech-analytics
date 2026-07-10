"""run_batch_analysis() — analyze N calls and surface trends (BONUS-A-TRENDS).

Why sequential, not concurrent, across calls (deliberate, unlike the intra-call agent fan-out
in `agents/supervisor.py`): each `run_analysis` runs its own faster-whisper pass, which is
CPU-bound and already saturates the 2-vCPU target host — the model is a shared warm singleton,
but inference activations and waveform buffers are per-concurrent-call. Running N calls
concurrently would oversubscribe the CPU (no wall-clock win on the dominant ASR stage, since
CPU is already the bottleneck) while multiplying peak memory, which is dangerous on a 2 GB VPS.
The supervisor's parallelism is a different situation: 4 network-bound LLM round-trips WITHIN
one call, where concurrency is free. So: intra-call parallel, inter-call sequential.
"""

from __future__ import annotations

import time
from typing import Any

from .agents import trends as trends_agent
from .agents.llm import LLMClient
from .analysis import run_analysis
from .errors import AnalysisError
from .logging_config import get_logger, log_event

logger = get_logger("mtbank.batch")

# Bounds the amplified fetch/CPU/SSRF surface of a batch endpoint (threat T-mue-01).
MAX_BATCH_SOURCES = 20

Source = str | tuple[Any, str]


def _normalize_source(source: Source) -> tuple[Any, str | None]:
    """A source is either a bare url/path string, or a (bytes|str, filename) tuple."""
    if isinstance(source, tuple):
        audio, filename = source[0], source[1] if len(source) > 1 else None
        return audio, filename
    return source, None


def _source_repr(source: Source) -> str:
    """Safe, human-readable label for the `errors` list — never the raw bytes payload."""
    if isinstance(source, tuple):
        return source[1] if len(source) > 1 and source[1] else "<bytes>"
    return str(source)


def run_batch_analysis(
    sources: list[Source], *, llm: LLMClient | None = None, request_id: str | None = None
) -> dict[str, Any]:
    """Analyze each source with the shared `run_analysis` core, then run the trends agent
    over the successes. One failing source never sinks the batch (decision 6)."""
    rid = request_id or f"batch-{int(time.time() * 1000)}"
    started = time.time()

    if len(sources) > MAX_BATCH_SOURCES:
        raise AnalysisError(
            f"Слишком много источников в батче (максимум {MAX_BATCH_SOURCES}).",
            code="batch_too_large",
        )

    log_event(logger, "batch_start", request_id=rid, num_sources=len(sources))

    calls: list[dict] = []
    errors: list[dict] = []
    for i, source in enumerate(sources):
        audio, filename = _normalize_source(source)
        call_rid = f"{rid}-{i}"
        try:
            calls.append(run_analysis(audio, filename=filename, request_id=call_rid, llm=llm))
        except AnalysisError as e:
            log_event(logger, "batch_call_failed", request_id=call_rid, code=e.code, error=e.message)
            errors.append({"source": _source_repr(source), "code": e.code, "message": e.message})
        except Exception as e:  # noqa: BLE001 — one bad call must never sink the batch
            log_event(logger, "batch_call_failed", request_id=call_rid, code="batch_call_failed",
                      error=str(e)[:300])
            errors.append({
                "source": _source_repr(source), "code": "batch_call_failed", "message": str(e)[:300],
            })

    try:
        trends = trends_agent.run(calls, llm or LLMClient(), request_id=rid)
    except Exception as e:  # noqa: BLE001 — the batch result must survive a dead trends agent too
        log_event(logger, "batch_trends_failed", request_id=rid, error=str(e)[:300])
        trends = trends_agent.fallback()

    result = {
        "calls": calls,
        "errors": errors,
        "trends": trends,
        "request_id": rid,
        "elapsed_s": round(time.time() - started, 2),
    }
    log_event(logger, "batch_done", request_id=rid, num_calls=len(calls), num_errors=len(errors),
              elapsed_s=result["elapsed_s"])
    return result
