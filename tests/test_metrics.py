"""Prometheus metrics — instrumentation point + /metrics exposition (BONUS-B-METRICS).

Counters are process-global and monotonic across the whole pytest session (module-level
Counter/Histogram objects live on the default REGISTRY for the process lifetime), so every
assertion here is a before/after DELTA — asserting an absolute value would make the suite
order-dependent and flaky.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from api.main import app
from mtbank.analysis import run_analysis
from mtbank.batch import run_batch_analysis

from .conftest import DEFAULT_RESPONSES, FakeLLM

client = TestClient(app)


def _sample(name: str, labels: dict | None = None) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_run_analysis_increments_calls_and_topic(monkeypatch, good_transcript, fake_llm):
    monkeypatch.setattr("mtbank.analysis._transcribe", lambda *a, **kw: good_transcript)

    before_calls = _sample("mtbank_calls_total")
    before_topic = _sample("mtbank_topic_total", {"topic": "кредиты"})

    run_analysis(b"x", llm=fake_llm)

    assert _sample("mtbank_calls_total") - before_calls == 1
    assert _sample("mtbank_topic_total", {"topic": "кредиты"}) - before_topic == 1


def test_run_batch_analysis_increments_calls_by_source_count(monkeypatch, good_transcript, fake_llm):
    monkeypatch.setattr("mtbank.analysis._transcribe", lambda *a, **kw: good_transcript)

    before_calls = _sample("mtbank_calls_total")

    run_batch_analysis([b"a", b"b"], llm=fake_llm)

    # Each successful source runs run_analysis once (design F) — the trends agent itself never
    # calls run_analysis, so no double count.
    assert _sample("mtbank_calls_total") - before_calls == 2


def test_compliance_failure_increments_compliance_failed_total(monkeypatch, good_transcript):
    responses = dict(DEFAULT_RESPONSES, compliance={"passed": False, "issues": ["x"]})
    llm = FakeLLM(responses=responses)
    monkeypatch.setattr("mtbank.analysis._transcribe", lambda *a, **kw: good_transcript)

    before = _sample("mtbank_compliance_failed_total")

    run_analysis(b"x", llm=llm)

    assert _sample("mtbank_compliance_failed_total") - before == 1


def test_degraded_agent_does_not_pollute_quality_or_topic(monkeypatch, good_transcript):
    """A dead LLM must not be reported as `quality=0, topic=другое` — that is a lying metric.

    The unknown score stays unknown (histogram count unchanged); the degradation is surfaced on
    mtbank_agent_failed_total instead.
    """
    llm = FakeLLM(fail=("classifier", "quality"))
    monkeypatch.setattr("mtbank.analysis._transcribe", lambda *a, **kw: good_transcript)

    before_calls = _sample("mtbank_calls_total")
    before_quality_count = _sample("mtbank_quality_score_count")
    before_topic = _sample("mtbank_topic_total", {"topic": "другое"})
    before_failed = _sample("mtbank_agent_failed_total", {"agent": "quality"})

    result = run_analysis(b"x", llm=llm)
    assert result["quality_score"]["total"] == 0          # the fallback really did fire
    assert result["classification"]["topic"] == "другое"

    assert _sample("mtbank_calls_total") - before_calls == 1               # the call happened
    assert _sample("mtbank_quality_score_count") - before_quality_count == 0   # but 0 is not data
    assert _sample("mtbank_topic_total", {"topic": "другое"}) - before_topic == 0
    assert _sample("mtbank_agent_failed_total", {"agent": "quality"}) - before_failed == 1


def test_compliance_fallback_is_not_counted_as_a_compliance_failure(monkeypatch, good_transcript):
    """compliance.fallback() returns passed=True, so it cannot inflate failures — but a degraded
    compliance agent must still not be silently treated as a clean call."""
    llm = FakeLLM(fail=("compliance",))
    monkeypatch.setattr("mtbank.analysis._transcribe", lambda *a, **kw: good_transcript)

    before_failures = _sample("mtbank_compliance_failed_total")
    before_degraded = _sample("mtbank_agent_failed_total", {"agent": "compliance"})

    run_analysis(b"x", llm=llm)

    assert _sample("mtbank_compliance_failed_total") - before_failures == 0
    assert _sample("mtbank_agent_failed_total", {"agent": "compliance"}) - before_degraded == 1


def test_metrics_endpoint_serves_prometheus_exposition_format():
    resp = client.get("/metrics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "version=0.0.4" in resp.headers["content-type"]
    assert "mtbank_calls_total" in resp.text
