"""Integration tests — supervisor orchestration and the full audio -> JSON pipeline (TEST-02)."""

from __future__ import annotations

import pytest

from mtbank.agents.supervisor import run_agents
from mtbank.analysis import run_analysis
from mtbank.errors import AudioDecodeError, AudioFetchError

from .conftest import TEST_DATA, FakeLLM

CONTRACT_KEYS = {
    "transcript", "classification", "quality_score", "compliance", "summary", "action_items",
}


# --------------------------------------------------------------------- supervisor
def test_supervisor_runs_all_four_agents(good_transcript, fake_llm):
    result = run_agents(good_transcript, fake_llm)
    assert sorted(fake_llm.calls) == ["classifier", "compliance", "quality", "summarizer"]
    assert CONTRACT_KEYS - {"transcript"} <= result.keys()
    assert "agent_errors" not in result


def test_supervisor_degrades_when_one_agent_fails(good_transcript):
    """A dead agent must not sink the analysis — its section degrades, the rest survive."""
    llm = FakeLLM(fail=("compliance",))
    result = run_agents(good_transcript, llm)

    assert result["compliance"] == {"passed": True, "issues": []}   # fallback
    assert result["classification"]["topic"] == "кредиты"           # unaffected
    assert result["quality_score"]["total"] == 80                   # unaffected
    assert any("compliance" in e for e in result["agent_errors"])


def test_supervisor_survives_every_agent_failing(good_transcript):
    llm = FakeLLM(fail=("classifier", "quality", "compliance", "summarizer"))
    result = run_agents(good_transcript, llm)

    assert len(result["agent_errors"]) == 4
    assert result["classification"] == {"topic": "другое", "priority": "medium"}
    assert result["quality_score"]["total"] == 0
    assert result["summary"] == "Резюме недоступно."


# --------------------------------------------------------------------- full pipeline
def test_run_analysis_returns_full_contract(monkeypatch, good_transcript, fake_llm):
    """audio -> JSON, with ASR stubbed so the test is fast and deterministic."""
    monkeypatch.setattr(
        "mtbank.analysis._transcribe", lambda src, name, rid: good_transcript
    )
    result = run_analysis(b"fake-audio", filename="call.wav", llm=fake_llm)

    assert CONTRACT_KEYS <= result.keys()
    assert result["transcript"] == good_transcript
    assert result["classification"] == {"topic": "кредиты", "priority": "medium"}
    assert result["quality_score"]["total"] == 80
    assert result["compliance"]["passed"] is True
    assert isinstance(result["action_items"], list)
    assert result["elapsed_s"] >= 0
    assert result["request_id"]


def test_transcript_segments_have_the_required_shape(monkeypatch, good_transcript, fake_llm):
    monkeypatch.setattr("mtbank.analysis._transcribe", lambda s, n, r: good_transcript)
    result = run_analysis("http://x/call.mp3", llm=fake_llm)

    for seg in result["transcript"]:
        assert set(seg) >= {"speaker", "start", "end", "text"}
        assert seg["speaker"] in ("Оператор", "Клиент")
        assert seg["end"] >= seg["start"]


# --------------------------------------------------------------------- error handling (ASR-05)
def test_unreachable_url_raises_fetch_error(fake_llm):
    with pytest.raises(AudioFetchError):
        run_analysis("https://example.invalid/nope.mp3", llm=fake_llm)


def test_undecodable_bytes_raise_decode_error(fake_llm):
    with pytest.raises(AudioDecodeError):
        run_analysis(b"this is definitely not audio", filename="call.wav", llm=fake_llm)


def test_empty_upload_raises_fetch_error(fake_llm):
    with pytest.raises(AudioFetchError):
        run_analysis(b"", filename="call.wav", llm=fake_llm)


# --------------------------------------------------------------------- real ASR (opt-in, slow)
@pytest.mark.slow
@pytest.mark.skipif(
    not (TEST_DATA / "call_dialog.mp3").exists(), reason="test audio not generated"
)
def test_real_audio_transcribes_and_diarizes(fake_llm):
    """Exercises faster-whisper + the diarizer for real. LLM still faked (no API key needed)."""
    result = run_analysis(str(TEST_DATA / "call_dialog.mp3"), llm=fake_llm)

    assert len(result["transcript"]) >= 5
    speakers = {s["speaker"] for s in result["transcript"]}
    assert speakers == {"Оператор", "Клиент"}, "both speakers must be detected"
    assert result["transcript"][0]["speaker"] == "Оператор", "the operator greets first"
    assert any("кредит" in s["text"].lower() for s in result["transcript"])
