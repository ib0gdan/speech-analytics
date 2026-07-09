"""Diarizer unit tests — the pyannote-free 2-speaker logic (ASR-04).

Synthetic tones stand in for voices: a high-pitch and a low-pitch sine are exactly the F0
difference the fingerprint is built to separate, with no ASR in the loop.
"""

from __future__ import annotations

import numpy as np
import pytest

from mtbank.asr.diarizer import CLIENT, OPERATOR, _assign_roles, _kmeans2, diarize
from mtbank.asr.audio import SAMPLE_RATE


def _tone(freq: float, seconds: float) -> np.ndarray:
    """A harmonic-rich tone: a sine plus overtones, so autocorrelation finds F0."""
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    wave = sum(np.sin(2 * np.pi * freq * k * t) / k for k in (1, 2, 3))
    return (0.3 * wave).astype(np.float32)


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


def test_empty_transcript_returns_empty():
    assert diarize([], np.zeros(100, dtype=np.float32)) == []


def test_single_segment_is_the_operator():
    segs = [{"start": 0.0, "end": 1.0, "text": "Добрый день"}]
    out = diarize(segs, _tone(200, 1.0))
    assert out[0]["speaker"] == OPERATOR


def test_two_pitches_separated_into_two_speakers():
    """220 Hz operator vs 120 Hz client, split by a 0.4 s pause."""
    waveform = np.concatenate([
        _tone(220, 2.0), _silence(0.4), _tone(120, 2.0),
        _silence(0.4), _tone(220, 2.0),
    ])
    segs = [
        {"start": 0.0, "end": 2.0, "text": "Добрый день, МТБанк, меня зовут Анна"},
        {"start": 2.4, "end": 4.4, "text": "Здравствуйте, хочу узнать про кредит"},
        {"start": 4.8, "end": 6.8, "text": "Уточните сумму, подскажу условия"},
    ]
    out = diarize(segs, waveform)

    assert [s["speaker"] for s in out] == [OPERATOR, CLIENT, OPERATOR]


def test_single_voice_is_not_split_into_two_speakers():
    waveform = np.concatenate([_tone(200, 2.0), _silence(0.4), _tone(200, 2.0)])
    segs = [
        {"start": 0.0, "end": 2.0, "text": "Добрый день"},
        {"start": 2.4, "end": 4.4, "text": "Чем могу помочь"},
    ]
    out = diarize(segs, waveform)
    assert {s["speaker"] for s in out} == {OPERATOR}


def test_kmeans_splits_two_obvious_clusters():
    x = np.array([[0.0], [0.1], [10.0], [10.1]], dtype=np.float32)
    labels = _kmeans2(x)
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]
    assert labels[0] != labels[2]


def test_roles_follow_operator_cues_not_speaking_order():
    """Even if the client speaks first, the bank's cues identify the operator."""
    turns = [
        {"text": "Здравствуйте, у меня вопрос"},          # cluster 0 — client
        {"text": "МТБанк, меня зовут Анна, чем могу помочь"},   # cluster 1 — operator
    ]
    role = _assign_roles(turns, np.array([0, 1]))
    assert role[1] == OPERATOR
    assert role[0] == CLIENT


def test_roles_fall_back_to_first_speaker_without_cues():
    turns = [{"text": "Алло"}, {"text": "Да, слушаю"}]
    role = _assign_roles(turns, np.array([0, 1]))
    assert role[0] == OPERATOR
