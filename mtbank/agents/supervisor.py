"""Supervisor — orchestrates the four agents (ORCH-01).

Why a hand-rolled supervisor instead of LangGraph
-------------------------------------------------
All four agents consume exactly one input (the diarized transcript) and produce disjoint slices
of the response. There are no cycles, no conditional edges, no shared mutable state — the graph
is a single fan-out/join. LangGraph exists to manage state machines with branching and loops;
adopting it here would pull the LangChain dependency stack into the pipelines container (which
already carries faster-whisper) to express a `ThreadPoolExecutor.map`. So: fan out the four
agents concurrently, join, merge.

Concurrency is what keeps us inside the <60 s budget: four sequential LLM round-trips would add
up, whereas in parallel the agent stage costs about as much as its slowest agent.

Resilience: one failing agent must not sink the whole analysis. Each agent has a `fallback()`;
a failure is logged, its section degrades, and the call is still returned with an `agent_errors`
list so the caller can see what was lost.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from ..logging_config import get_logger, log_event
from . import classifier, compliance, quality, summarizer
from .llm import LLMClient

logger = get_logger("mtbank.agents.supervisor")

# (result key(s), module) — each module exposes run(transcript, llm, request_id) and fallback()
_AGENTS: list[tuple[str, Any]] = [
    ("classification", classifier),
    ("quality_score", quality),
    ("compliance", compliance),
    ("summary", summarizer),          # produces both `summary` and `action_items`
]


def _run_one(
    key: str, module: Any, transcript: list[dict], llm: LLMClient, request_id: str
) -> tuple[str, dict, str | None]:
    try:
        return key, module.run(transcript, llm, request_id), None
    except Exception as e:  # noqa: BLE001 — degrade this agent, keep the rest
        log_event(logger, "agent_failed", request_id=request_id,
                  agent=module.NAME, error=str(e)[:300])
        return key, module.fallback(), f"{module.NAME}: {e}"


def run_agents(
    transcript: list[dict], llm: LLMClient | None = None, *, request_id: str = "-"
) -> dict[str, Any]:
    """Fan out the four agents over the transcript, join, and merge into the contract."""
    llm = llm or LLMClient()
    log_event(logger, "agents_start", request_id=request_id,
              agents=[m.NAME for _, m in _AGENTS], segments=len(transcript))

    with ThreadPoolExecutor(max_workers=len(_AGENTS)) as pool:
        results = list(
            pool.map(lambda a: _run_one(a[0], a[1], transcript, llm, request_id), _AGENTS)
        )

    merged: dict[str, Any] = {}
    errors: list[str] = []
    for key, value, error in results:
        if error:
            errors.append(error)
        if key == "summary":                       # summarizer fills two contract fields
            merged["summary"] = value["summary"]
            merged["action_items"] = value["action_items"]
        else:
            merged[key] = value

    if errors:
        merged["agent_errors"] = errors

    log_event(logger, "agents_done", request_id=request_id,
              failed=len(errors), topic=merged["classification"]["topic"],
              quality_total=merged["quality_score"]["total"],
              compliance_passed=merged["compliance"]["passed"])
    return merged
