"""REST surface tests — POST /analyze contract and error codes (API-01, ASR-05)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from mtbank.errors import AudioFetchError

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze_rejects_missing_body():
    assert client.post("/analyze", json={}).status_code == 400


def test_analyze_rejects_unsupported_content_type():
    resp = client.post("/analyze", content=b"raw", headers={"Content-Type": "text/plain"})
    assert resp.status_code == 415


def test_analyze_json_url_returns_contract(monkeypatch):
    monkeypatch.setattr(
        "api.main.run_analysis",
        lambda src, **kw: {"transcript": [], "classification": {"topic": "карты",
                                                                "priority": "high"}},
    )
    resp = client.post("/analyze", json={"url": "https://x/call.mp3"})
    assert resp.status_code == 200
    assert resp.json()["classification"]["topic"] == "карты"


def test_analyze_multipart_file_is_read_as_bytes(monkeypatch):
    seen = {}

    def fake(src, **kw):
        seen["src"], seen["filename"] = src, kw.get("filename")
        return {"transcript": []}

    monkeypatch.setattr("api.main.run_analysis", fake)
    resp = client.post("/analyze", files={"file": ("call.wav", b"AUDIOBYTES", "audio/wav")})

    assert resp.status_code == 200
    assert seen["src"] == b"AUDIOBYTES"
    assert seen["filename"] == "call.wav"


def test_analysis_error_becomes_400_with_code(monkeypatch):
    def boom(src, **kw):
        raise AudioFetchError("Не удалось скачать аудио по ссылке")

    monkeypatch.setattr("api.main.run_analysis", boom)
    resp = client.post("/analyze", json={"url": "https://bad/x.mp3"})

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "audio_fetch_error"
