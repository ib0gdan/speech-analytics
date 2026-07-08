"""FastAPI REST surface — POST /analyze.

Reuses the SAME shared core (mtbank.analysis.run_analysis) as the OpenWebUI Pipeline, so the
chat path and the REST path can never drift (CORE-01, API-01). Accepts either a multipart file
upload or a JSON/form `url`.
"""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Request

from mtbank import __version__
from mtbank.analysis import run_analysis
from mtbank.logging_config import get_logger, log_event

logger = get_logger("mtbank.api")

app = FastAPI(title="MTBank Call Analytics API", version=__version__)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mtbank-api", "version": __version__, "stub": True}


@app.post("/analyze")
async def analyze(request: Request) -> dict:
    """Analyze a call. Body: multipart `file` (and/or `url`), OR JSON `{"url": "..."}`."""
    rid = f"api-{int(time.time() * 1000)}"
    content_type = request.headers.get("content-type", "")
    url: str | None = None
    filename: str | None = None

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
    else:
        raise HTTPException(
            status_code=415,
            detail="Use multipart/form-data (file/url) or application/json ({\"url\": ...}).",
        )

    if not url and not filename:
        raise HTTPException(status_code=400, detail="Provide an audio `file` or a `url`.")

    audio_source = url or filename
    log_event(logger, "analyze_request", request_id=rid,
              has_file=filename is not None, url=url, content_type=content_type)

    # Phase 1 skeleton: audio is not downloaded/transcribed yet — the contract is what matters.
    result = run_analysis(audio_source, request_id=rid)
    return result
