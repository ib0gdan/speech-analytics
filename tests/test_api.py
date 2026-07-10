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


# --------------------------------------------------------------------- /analyze-batch (BONUS-A-TRENDS)
def test_analyze_batch_json_urls_returns_trends(monkeypatch):
    seen = {}

    def fake(sources, **kw):
        seen["sources"] = sources
        return {
            "calls": [{"classification": {"topic": "карты"}}, {"classification": {"topic": "кредиты"}}],
            "errors": [],
            "trends": {"num_calls": 2, "topics": {"карты": 1, "кредиты": 1}},
            "request_id": kw.get("request_id"),
            "elapsed_s": 1.23,
        }

    monkeypatch.setattr("api.main.run_batch_analysis", fake)
    resp = client.post("/analyze-batch", json={"urls": ["http://x/a.mp3", "http://x/b.wav"]})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["calls"]) == 2
    assert body["trends"]["num_calls"] == 2
    assert seen["sources"] == ["http://x/a.mp3", "http://x/b.wav"]


def test_analyze_batch_rejects_empty_body():
    assert client.post("/analyze-batch", json={"urls": []}).status_code == 400
