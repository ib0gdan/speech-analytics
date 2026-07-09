"""Unit tests — one per agent (TEST-01).

These assert OUR logic, not the model's taste: whitelist coercion, deterministic scoring,
two-layer compliance merging, and output sanitisation. The LLM is faked.
"""

from __future__ import annotations

import pytest

from mtbank.agents import classifier, compliance, quality, summarizer

from .conftest import FakeLLM


# --------------------------------------------------------------------- 🏷️ classifier
def test_classifier_returns_topic_and_priority(good_transcript, fake_llm):
    result = classifier.run(good_transcript, fake_llm)
    assert result == {"topic": "кредиты", "priority": "medium"}
    assert fake_llm.calls == ["classifier"]


def test_classifier_coerces_unknown_values(good_transcript):
    """A model that invents a topic must not leak it into the contract."""
    llm = FakeLLM({"classifier": {"topic": "ипотека", "priority": "urgent"}})
    result = classifier.run(good_transcript, llm)
    assert result == {"topic": "другое", "priority": "medium"}


def test_classifier_survives_missing_fields(good_transcript):
    llm = FakeLLM({"classifier": {}})
    assert classifier.run(good_transcript, llm) == {"topic": "другое", "priority": "medium"}


# --------------------------------------------------------------------- ⭐ quality
@pytest.mark.parametrize(
    "checklist, expected",
    [
        ({"greeting": True, "need_detection": True, "solution_provided": True, "farewell": True}, 100),
        ({"greeting": False, "need_detection": False, "solution_provided": False, "farewell": False}, 0),
        ({"greeting": True, "need_detection": True, "solution_provided": True, "farewell": False}, 80),
        ({"greeting": True, "need_detection": False, "solution_provided": False, "farewell": True}, 40),
    ],
)
def test_quality_total_is_deterministic_weighted_sum(checklist, expected):
    """The score is computed in code, never taken from the model."""
    assert quality.compute_total(checklist) == expected


def test_quality_weights_sum_to_100():
    assert sum(quality.WEIGHTS.values()) == 100


def test_quality_run_maps_booleans_and_scores(good_transcript, fake_llm):
    result = quality.run(good_transcript, fake_llm)
    assert result["checklist"] == {
        "greeting": True, "need_detection": True, "solution_provided": True, "farewell": False,
    }
    assert result["total"] == 80        # 20 + 30 + 30, farewell missing


def test_quality_treats_missing_keys_as_false(good_transcript):
    llm = FakeLLM({"quality": {"greeting": True}})
    result = quality.run(good_transcript, llm)
    assert result["total"] == 20
    assert result["checklist"]["farewell"] is False


# --------------------------------------------------------------------- 🛡️ compliance
def test_compliance_deterministic_layer_catches_forbidden_phrases(bad_transcript):
    """Rule layer alone — no LLM involved — must catch every known-forbidden phrase."""
    issues = compliance.check_forbidden(bad_transcript)
    assert len(issues) == 4
    assert any("гарантирую одобрение" in i for i in issues)
    assert any("никаких рисков" in i for i in issues)


def test_compliance_ignores_client_speech():
    """A client may say anything; only the operator is under compliance."""
    transcript = [{"speaker": "Клиент", "start": 0, "end": 2,
                   "text": "Вы же гарантирую одобрение обещали?"}]
    assert compliance.check_forbidden(transcript) == []


def test_compliance_fails_when_rules_fire_even_if_llm_says_passed(bad_transcript):
    """A lenient model cannot override the deterministic layer."""
    llm = FakeLLM({"compliance": {"passed": True, "issues": []}})
    result = compliance.run(bad_transcript, llm)
    assert result["passed"] is False
    assert len(result["issues"]) == 4


def test_compliance_merges_both_layers_without_duplicates(bad_transcript):
    llm = FakeLLM({"compliance": {"passed": False, "issues": ["Отсутствует disclaimer"]}})
    result = compliance.run(bad_transcript, llm)
    assert result["passed"] is False
    assert "Отсутствует disclaimer" in result["issues"]
    assert len(result["issues"]) == 5       # 4 rule-based + 1 from the LLM


def test_compliance_passes_clean_call(good_transcript, fake_llm):
    result = compliance.run(good_transcript, fake_llm)
    assert result == {"passed": True, "issues": []}


# --------------------------------------------------------------------- 📝 summarizer
def test_summarizer_returns_summary_and_action_items(good_transcript, fake_llm):
    result = summarizer.run(good_transcript, fake_llm)
    assert result["summary"].startswith("Клиент спросил")
    assert result["action_items"] == ["Отправить условия на email"]


def test_summarizer_drops_blank_items_and_caps_the_list(good_transcript):
    llm = FakeLLM({"summarizer": {"summary": "Резюме.",
                                  "action_items": ["a", "  ", "b", "c", "d", "e", "f", "g"]}})
    result = summarizer.run(good_transcript, llm)
    assert "  " not in result["action_items"]
    assert len(result["action_items"]) == summarizer._MAX_ACTION_ITEMS


def test_summarizer_falls_back_on_empty_summary(good_transcript):
    llm = FakeLLM({"summarizer": {"summary": "", "action_items": []}})
    assert summarizer.run(good_transcript, llm)["summary"] == "Резюме недоступно."


# --------------------------------------------------------------------- fallbacks
@pytest.mark.parametrize("module", [classifier, quality, compliance, summarizer])
def test_every_agent_exposes_a_usable_fallback(module):
    """The supervisor relies on these when an agent dies."""
    assert isinstance(module.fallback(), dict)
    assert module.NAME
