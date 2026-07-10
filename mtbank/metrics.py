"""Prometheus metrics — one instrumentation point, two scrape targets (BONUS-B-METRICS).

`pipelines` (chat) and `api` (REST) are separate processes with separate in-memory registries —
a single uvicorn worker each, so one process = one registry (no pushgateway, no multiprocess
mode; stated honestly in README). `run_analysis` is the one function BOTH import, so calling
`record_analysis` there — and only there — is the single point that covers chat, REST, and batch
(mtbank.batch.run_batch_analysis calls run_analysis per source). The true combined total only
exists once Prometheus scrapes both `api:8000/metrics` and `pipelines:9100/metrics` and the
dashboard sums across them.

Graceful-optional: if prometheus_client is ever unavailable, every public function below becomes
a no-op. Observability must never be able to sink the core audio->JSON path (matches the
project's warmup/agent-fallback resilience style, T-nc0-04).
"""

from __future__ import annotations

from typing import Any

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Histogram,
        generate_latest,
        start_http_server,
    )

    _ENABLED = True
except ImportError:  # pragma: no cover — exercised only if the dependency is missing
    _ENABLED = False

# The classifier already guarantees topic is one of these five (mtbank/agents/classifier.py);
# this whitelist is defence in depth against a future upstream change, keeping the Prometheus
# label cardinality bounded (design C — never request_id/url/filename as a label).
_TOPICS = ("кредиты", "карты", "переводы", "жалобы", "другое")

# Bounded label set, mirroring the agent modules' NAME constants.
_AGENTS = ("classifier", "quality", "compliance", "summarizer")

if _ENABLED:
    CALLS_TOTAL = Counter("mtbank_calls_total", "Total analyzed calls (chat + REST + batch).")
    TOPIC_TOTAL = Counter(
        "mtbank_topic_total", "Analyzed calls by classified topic.", ["topic"]
    )
    COMPLIANCE_FAILED_TOTAL = Counter(
        "mtbank_compliance_failed_total", "Calls where the compliance layer failed."
    )
    AGENT_FAILED_TOTAL = Counter(
        "mtbank_agent_failed_total", "Calls where an agent degraded to its fallback.", ["agent"]
    )
    # Score support is the discrete set {0,20,30,40,50,60,70,80,100} (fixed weights
    # 20/30/30/20) — a Histogram's bucket counters sum across the two scrape targets, unlike a
    # Summary's per-instance quantiles (design D).
    QUALITY_SCORE = Histogram(
        "mtbank_quality_score", "Quality checklist score (0-100).",
        buckets=(20, 40, 60, 80, 100),
    )
    ANALYSIS_DURATION_SECONDS = Histogram(
        "mtbank_analysis_duration_seconds", "run_analysis wall-clock duration, seconds.",
        buckets=(5, 10, 15, 20, 30, 45, 60, 90, 120),
    )


def _failed_agents(result: dict[str, Any]) -> set[str]:
    """Agents that degraded to their fallback, from the supervisor's `f"{NAME}: {error}"` list."""
    failed = {str(e).split(":", 1)[0].strip() for e in result.get("agent_errors", [])}
    return failed & set(_AGENTS)


def record_analysis(result: dict[str, Any], duration_s: float) -> None:
    """Increment/observe metrics from a full run_analysis() result. Never mutates `result`.

    A degraded agent's fallback is NOT data. `quality.fallback()` returns total=0 and
    `classifier.fallback()` returns "другое" — recording those would report a dead LLM as
    "operators scored 0" and inflate the "другое" topic, i.e. the metric would lie precisely
    when the system is unhealthy. So a failed agent's slice is SKIPPED and surfaced on
    `mtbank_agent_failed_total` instead: an unknown score stays unknown, and the gap between
    `mtbank_calls_total` and `mtbank_quality_score_count` is exactly the degradation.
    """
    if not _ENABLED:
        return

    failed = _failed_agents(result)
    CALLS_TOTAL.inc()
    for agent in failed:
        AGENT_FAILED_TOTAL.labels(agent=agent).inc()

    if "classifier" not in failed:
        topic = result.get("classification", {}).get("topic")
        TOPIC_TOTAL.labels(topic=topic if topic in _TOPICS else "другое").inc()

    if "compliance" not in failed and result.get("compliance", {}).get("passed") is False:
        COMPLIANCE_FAILED_TOTAL.inc()

    if "quality" not in failed:
        QUALITY_SCORE.observe(result.get("quality_score", {}).get("total", 0))

    # The wall-clock is measured by us, not by an agent — always real, always recorded.
    ANALYSIS_DURATION_SECONDS.observe(duration_s)


def render() -> tuple[bytes, str]:
    """Prometheus text exposition of the default registry, for a `/metrics` route."""
    if not _ENABLED:
        return b"", "text/plain"
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def start_exporter(port: int) -> None:
    """Start an in-process HTTP exporter (used by `pipelines`, which has no FastAPI route we
    can hook — OpenWebUI owns that app). No-op when prometheus_client is unavailable."""
    if not _ENABLED:
        return
    start_http_server(port)
