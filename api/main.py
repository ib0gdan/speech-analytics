"""FastAPI REST surface — POST /analyze.

Reuses the SAME shared core (mtbank.analysis.run_analysis) as the OpenWebUI Pipeline, so the
chat path and the REST path can never drift (CORE-01, API-01). Accepts either a multipart file
upload or a JSON/form `url`.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from mtbank import __version__
from mtbank.analysis import run_analysis
from mtbank.asr.transcriber import warmup
from mtbank.errors import AnalysisError
from mtbank.logging_config import get_logger, log_event

logger = get_logger("mtbank.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Preload whisper so the first /analyze call doesn't pay the model download (~70 s cold).
    try:
        warmup()
        log_event(logger, "whisper_preloaded")
    except Exception as e:  # noqa: BLE001 — a warm-up failure must not stop the service
        log_event(logger, "whisper_preload_failed", error=str(e)[:200])
    yield


app = FastAPI(title="MTBank Call Analytics API", version=__version__, lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mtbank-api", "version": __version__}


@app.post("/analyze")
async def analyze(request: Request) -> dict:
    """Analyze a call. Body: multipart `file` (or `url`), OR JSON `{"url": "..."}`."""
    rid = f"api-{int(time.time() * 1000)}"
    content_type = request.headers.get("content-type", "")
    url: str | None = None
    filename: str | None = None
    payload: bytes | None = None

    if content_type.startswith("application/json"):
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Invalid JSON body.")
        url = (body or {}).get("url")
    elif content_type.startswith("multipart/form-data"):
        form = await request.form()
        url = form.get("url")
        upload = form.get("file")
        if upload is not None and hasattr(upload, "filename"):
            filename = upload.filename
            payload = await upload.read()
    else:
        raise HTTPException(
            status_code=415,
            detail="Use multipart/form-data (file/url) or application/json ({\"url\": ...}).",
        )

    if not url and not payload:
        raise HTTPException(status_code=400, detail="Provide an audio `file` or a `url`.")

    log_event(logger, "analyze_request", request_id=rid,
              has_file=payload is not None, url=url, content_type=content_type)

    try:
        return run_analysis(payload or url, filename=filename, request_id=rid)
    except AnalysisError as e:
        log_event(logger, "analyze_failed", request_id=rid, code=e.code, error=e.message)
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
