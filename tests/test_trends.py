"""Unit tests — 📊 trends agent + batch core (BONUS-A-TRENDS).

Mirrors tests/test_agents.py in spirit: assert OUR logic (deterministic aggregation, LLM-output
coercion, batch resilience), never the model's taste. The LLM is faked throughout — trends.run
must never be exercised against the real network in a test.
"""

from __future__ import annotations

import pytest

from mtbank import batch as batch_module
from mtbank.agents import compliance, trends
from mtbank.errors import AnalysisError

from .conftest import FakeLLM


def _call(
    *,
    topic="кредиты",
    quality_total=80,
    checklist=None,
    compliance_passed=True,
    compliance_issues=None,
    transcript=None,
    action_items=None,
):
    """Fabricate a run_analysis()-shaped result dict — only the fields trends reads."""
    return {
        "transcript": transcript if transcript is not None else [],
        "classification": {"topic": topic, "priority": "medium"},
        "quality_score": {
            "total": quality_total,
            "checklist": checklist
            if checklist is not None
            else {"greeting": True, "need_detection": True, "solution_provided": True, "farewell": True},
        },
        "compliance": {"passed": compliance_passed, "issues": compliance_issues or []},
        "summary": "Резюме.",
        "action_items": action_items or [],
    }


@pytest.fixture
def good_transcript_no_forbidden() -> list[dict]:
    return [
        {"speaker": "Оператор", "start": 0.0, "end": 4.0,
         "text": "Добрый день, МТБанк, меня зовут Анна."},
        {"speaker": "Клиент", "start": 4.0, "end": 8.0, "text": "Хочу узнать про кредит."},
    ]


@pytest.fixture
def three_calls(bad_transcript, good_transcript_no_forbidden) -> list[dict]:
    """A ~ good/кредиты (80), B ~ bad/карты, compliance failed, forbidden phrases (60),
    C ~ good/кредиты, perfect (100)."""
    call_a = _call(
        topic="кредиты",
        quality_total=80,
        checklist={"greeting": True, "need_detection": True, "solution_provided": True, "farewell": False},
        compliance_passed=True,
        transcript=good_transcript_no_forbidden,
        action_items=["Отправить условия"],
    )
    call_b = _call(
        topic="карты",
        quality_total=60,
        checklist={"greeting": True, "need_detection": False, "solution_provided": True, "farewell": True},
        compliance_passed=False,
        compliance_issues=["Отсутствует disclaimer"],
        transcript=bad_transcript,
        action_items=[],
    )
    call_c = _call(
        topic="кредиты",
        quality_total=100,
        checklist={"greeting": True, "need_detection": True, "solution_provided": True, "farewell": True},
        compliance_passed=True,
        transcript=good_transcript_no_forbidden,
        action_items=["Перевыпустить карту"],
    )
    return [call_a, call_b, call_c]


# --------------------------------------------------------------------- compute_aggregates
def test_compute_aggregates_over_three_calls(three_calls):
    agg = trends.compute_aggregates(three_calls)

    assert agg["num_calls"] == 3
    assert agg["topics"] == {"кредиты": 2, "карты": 1}
    assert agg["quality"] == {"avg": 80.0, "min": 60, "max": 100}
    assert agg["checklist_pass_rate"] == {
        "greeting": 1.0,
        "need_detection": round(2 / 3, 4),
        "solution_provided": 1.0,
        "farewell": round(2 / 3, 4),
    }
    assert agg["compliance_failure_rate"] == round(1 / 3, 4)


def test_compute_aggregates_forbidden_phrase_hits_reuses_check_forbidden(three_calls, bad_transcript):
    """Decision 2: tally comes from compliance.check_forbidden, not from parsed issue strings."""
    agg = trends.compute_aggregates(three_calls)

    expected_issues = compliance.check_forbidden(bad_transcript)
    assert len(expected_issues) == 4  # sanity: matches test_agents.py's known count

    assert sum(agg["forbidden_phrase_hits"].values()) == 4
    for issue in expected_issues:
        assert agg["forbidden_phrase_hits"][issue] == 1


def test_compute_aggregates_clean_batch_has_no_forbidden_hits(good_transcript_no_forbidden):
    calls = [_call(transcript=good_transcript_no_forbidden)]
    agg = trends.compute_aggregates(calls)
    assert agg["forbidden_phrase_hits"] == {}


def test_compute_aggregates_empty_list_is_safe():
    agg = trends.compute_aggregates([])
    assert agg["num_calls"] == 0
    assert agg["topics"] == {}
    assert agg["quality"] == {"avg": None, "min": None, "max": None}
    assert agg["checklist_pass_rate"] == {}
    assert agg["compliance_failure_rate"] == 0.0
    assert agg["forbidden_phrase_hits"] == {}


def test_compute_aggregates_single_call_is_sane(good_transcript_no_forbidden):
    calls = [_call(quality_total=75, transcript=good_transcript_no_forbidden)]
    agg = trends.compute_aggregates(calls)
    assert agg["num_calls"] == 1
    assert agg["topics"] == {"кредиты": 1}
    assert agg["quality"] == {"avg": 75.0, "min": 75, "max": 75}


def test_compute_aggregates_survives_a_degraded_call():
    """A call carrying agent_errors / missing sections must not crash aggregation."""
    degraded = {"transcript": [], "agent_errors": ["classifier: boom"]}
    calls = [_call(), degraded]
    agg = trends.compute_aggregates(calls)
    assert agg["num_calls"] == 2
    assert agg["topics"]["другое"] == 1  # missing classification -> default topic


# --------------------------------------------------------------------- trends.run — LLM layer
def test_trends_run_empty_calls_returns_safe_defaults_without_calling_llm():
    llm = FakeLLM()
    result = trends.run([], llm)
    assert result["num_calls"] == 0
    assert result["patterns"] == []
    assert llm.calls == []


def test_trends_run_merges_llm_judgement_with_aggregates(three_calls):
    llm = FakeLLM()
    result = trends.run(three_calls, llm)

    assert llm.calls == ["trends"]
    assert result["patterns"] == FakeLLM().responses["trends"]["patterns"]
    assert result["recommendations"] == FakeLLM().responses["trends"]["recommendations"]
    # deterministic aggregates present in the SAME dict
    assert result["num_calls"] == 3
    assert result["quality"]["avg"] == 80.0


def test_trends_run_degrades_to_empty_judgement_on_llm_failure(three_calls):
    """The critical test: aggregates must survive even when the LLM call raises."""
    llm = FakeLLM(fail=("trends",))
    result = trends.run(three_calls, llm)

    assert result["num_calls"] == 3
    assert result["topics"] == {"кредиты": 2, "карты": 1}
    assert result["quality"]["avg"] == 80.0
    assert result["patterns"] == []
    assert result["causes"] == []
    assert result["recommendations"] == []
    assert result["grouped_action_items"] == []
    assert result["grouped_compliance_issues"] == []


def test_trends_run_coerces_garbage_llm_response(three_calls):
    llm = FakeLLM({"trends": {"patterns": "не список", "recommendations": [1, 2, None, "  ", "ok"]}})
    result = trends.run(three_calls, llm)

    assert result["patterns"] == []          # non-list value -> []
    assert result["recommendations"] == ["ok"]  # ints/None/blank dropped, non-empty str kept
    assert result["causes"] == []            # missing key -> []
    # aggregates still correct alongside the coerced judgement
    assert result["num_calls"] == 3


def test_trends_fallback_returns_full_safe_shape():
    fb = trends.fallback()
    assert fb["num_calls"] == 0
    assert fb["patterns"] == []
    assert fb["quality"] == {"avg": None, "min": None, "max": None}


def test_trends_name_is_set():
    assert trends.NAME == "trends"


# --------------------------------------------------------------------- run_batch_analysis
def test_run_batch_analysis_reuses_run_analysis_and_survives_one_failure(monkeypatch, three_calls):
    def fake_run_analysis(audio, **kwargs):
        if audio == "bad":
            raise AnalysisError("Не удалось скачать аудио.", code="audio_fetch_error")
        return three_calls[0] if audio == "ok1" else three_calls[2]

    monkeypatch.setattr(batch_module, "run_analysis", fake_run_analysis)

    result = batch_module.run_batch_analysis(["ok1", "bad", "ok2"], llm=FakeLLM())

    assert len(result["calls"]) == 2
    assert len(result["errors"]) == 1
    assert result["errors"][0]["code"] == "audio_fetch_error"
    assert result["trends"]["num_calls"] == 2
    assert "request_id" in result
    assert result["elapsed_s"] >= 0


def test_run_batch_analysis_all_fail_returns_safe_empty_trends(monkeypatch):
    def always_fails(audio, **kwargs):
        raise AnalysisError("боль", code="audio_fetch_error")

    monkeypatch.setattr(batch_module, "run_analysis", always_fails)

    result = batch_module.run_batch_analysis(["a", "b"], llm=FakeLLM())

    assert result["calls"] == []
    assert len(result["errors"]) == 2
    assert result["trends"]["num_calls"] == 0


def test_run_batch_analysis_enforces_max_sources():
    """Decision 7 / threat T-mue-01: over-cap batches are rejected before any call runs."""
    sources = ["x"] * (batch_module.MAX_BATCH_SOURCES + 1)
    with pytest.raises(AnalysisError) as exc:
        batch_module.run_batch_analysis(sources, llm=FakeLLM())
    assert exc.value.code == "batch_too_large"
