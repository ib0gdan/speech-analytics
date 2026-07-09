"""OpenAI-compatible LLM client (Groq by default).

Why Groq: the four agents run per call and must fit the <60 s budget alongside ASR. Groq's
free tier serves llama-3.3-70b at very high tokens/s and speaks the OpenAI API, so the provider
is swappable via `LLM_BASE_URL` without touching agent code.

Every call is logged as structured JSON with the agent's input and output (INFRA-04).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

from ..errors import AnalysisError
from ..logging_config import get_logger, log_event

logger = get_logger("mtbank.agents.llm")

_TIMEOUT = 45
_RETRIES = 2
_MAX_LOG_CHARS = 600


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    def complete_json(
        self, system: str, user: str, *, agent: str, request_id: str = "-"
    ) -> dict[str, Any]:
        """Call the LLM in JSON mode and return the parsed object."""
        if not self.api_key:
            raise AnalysisError(
                "LLM не настроен: не задан GROQ_API_KEY.", code="llm_not_configured"
            )

        payload = {
            "model": self.model,
            "temperature": 0,                       # deterministic: same call -> same verdict
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        log_event(logger, "agent_input", request_id=request_id, agent=agent,
                  model=self.model, input=user[:_MAX_LOG_CHARS])

        last_error: Exception | None = None
        for attempt in range(1, _RETRIES + 2):
            started = time.time()
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload, headers=headers, timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                log_event(logger, "agent_output", request_id=request_id, agent=agent,
                          elapsed_s=round(time.time() - started, 2),
                          output=json.dumps(parsed, ensure_ascii=False)[:_MAX_LOG_CHARS])
                return parsed
            except Exception as e:  # noqa: BLE001 — network, HTTP, or malformed JSON
                last_error = e
                log_event(logger, "agent_retry", request_id=request_id, agent=agent,
                          attempt=attempt, error=str(e)[:200])

        raise AnalysisError(
            f"Агент «{agent}» не смог получить ответ от LLM: {last_error}", code="llm_failed"
        )


def format_transcript(transcript: list[dict]) -> str:
    """Render the diarized transcript the way every agent sees it."""
    return "\n".join(f"{s['speaker']}: {s['text']}" for s in transcript)
