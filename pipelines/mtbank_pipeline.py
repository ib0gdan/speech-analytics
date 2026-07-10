"""
title: MTBank Call Analytics
author: ib0gdan
description: If the message contains an audio URL, the pipe transcribes the call
             (faster-whisper + Оператор/Клиент diarization) and returns the full analysis
             rendered as chat markdown, via the shared mtbank.analysis.run_analysis core.
             Otherwise it forwards the message to Groq.
             NOTE: `requirements:` above must stay a bare package list — the pipelines
             server feeds the whole line to pip, so an inline comment breaks the install
             and the server then quarantines this file into pipelines/failed/.
             faster-whisper and numpy are baked into Dockerfile.pipelines instead.
requirements: requests
"""

import os
import re
from typing import List, Union, Generator, Iterator

import requests
from pydantic import BaseModel

from mtbank.analysis import run_analysis  # shared core, mounted at /app/mtbank
from mtbank.errors import AnalysisError

_AUDIO_URL_RE = re.compile(r"https?://\S+\.(?:wav|mp3|ogg|m4a|flac)", re.IGNORECASE)

# Chat-only labels. The JSON contract returned by /analyze keeps its English keys — the task
# fixes that schema (quality_score.checklist.greeting, ...), so only the rendering is localised.
_PRIORITY_RU = {"low": "низкий", "medium": "средний", "high": "высокий"}
_CHECKLIST_RU = {
    "greeting": "приветствие",
    "need_detection": "выявление потребности",
    "solution_provided": "решение предложено",
    "farewell": "прощание",
}


def _format_markdown(result: dict) -> str:
    """Render the analysis contract as readable chat markdown (Russian)."""
    header = "## 📞 Анализ звонка"
    if result.get("elapsed_s") is not None:
        header += f" _(обработка {result['elapsed_s']} с)_"
    lines = [header]

    lines.append("\n### Транскрипт")
    for seg in result["transcript"]:
        lines.append(f"- **{seg['speaker']}** [{seg['start']:.1f}–{seg['end']:.1f} с]: {seg['text']}")

    c = result["classification"]
    priority = _PRIORITY_RU.get(c["priority"], c["priority"])
    lines.append(f"\n### Классификация\n- Тема: **{c['topic']}** · Приоритет: **{priority}**")

    q = result["quality_score"]
    checks = " · ".join(
        f"{_CHECKLIST_RU.get(k, k)}: {'✅' if v else '❌'}" for k, v in q["checklist"].items()
    )
    lines.append(f"\n### Качество обслуживания: **{q['total']}/100**\n- {checks}")

    comp = result["compliance"]
    lines.append(f"\n### Комплаенс: {'✅ нарушений нет' if comp['passed'] else '❌ есть нарушения'}")
    if comp["issues"]:
        lines.append("\n".join(f"  - {i}" for i in comp["issues"]))

    lines.append(f"\n### Резюме\n{result['summary']}")

    items = result["action_items"]
    body = "\n".join(f"- {a}" for a in items) if items else "- нет"
    lines.append(f"\n### Задачи после звонка\n{body}")

    if result.get("agent_errors"):
        lines.append("\n> ⚠️ Часть агентов не отработала: " + "; ".join(result["agent_errors"]))
    return "\n".join(lines)


class Pipeline:
    class Valves(BaseModel):
        LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
        LLM_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        # ASR: `small` int8 keeps a 5-min call under the 60s budget on CPU; `medium` overshoots.
        WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
        WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    def __init__(self):
        self.name = "MTBank Call Analytics"
        self.valves = self.Valves()

    async def on_startup(self):
        status = "OK" if self.valves.LLM_API_KEY else "NO GROQ_API_KEY"
        print(f"[{self.name}] on_startup — model={self.valves.LLM_MODEL} key={status}")

        # Load whisper now, not on the first user's request: on a cold container that cost 70s
        # and blew the 60s response budget for whoever happened to be first.
        os.environ.setdefault("WHISPER_MODEL", self.valves.WHISPER_MODEL)
        os.environ.setdefault("WHISPER_COMPUTE_TYPE", self.valves.WHISPER_COMPUTE_TYPE)
        try:
            from mtbank.asr.transcriber import warmup

            warmup()
            print(f"[{self.name}] whisper '{self.valves.WHISPER_MODEL}' preloaded")
        except Exception as e:  # noqa: BLE001 — a warm-up failure must never block startup
            print(f"[{self.name}] whisper preload failed: {e}")

    async def on_shutdown(self):
        print(f"[{self.name}] on_shutdown")

    def _chat_groq(self, messages: List[dict], stream: bool):
        if not self.valves.LLM_API_KEY:
            return ("⚠️ GROQ_API_KEY не задан. Вставьте ключ (https://console.groq.com) в `.env` "
                    "и перезапустите: `docker compose up -d`.")
        headers = {"Authorization": f"Bearer {self.valves.LLM_API_KEY}",
                   "Content-Type": "application/json"}
        payload = {"model": self.valves.LLM_MODEL, "messages": messages, "stream": stream}
        try:
            resp = requests.post(f"{self.valves.LLM_BASE_URL}/chat/completions",
                                 json=payload, headers=headers, stream=stream, timeout=60)
            resp.raise_for_status()
            return resp.iter_lines() if stream else resp.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            return f"Ошибка обращения к LLM ({self.valves.LLM_MODEL}): {e}"

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Union[str, Generator, Iterator]:
        match = _AUDIO_URL_RE.search(user_message or "")
        if match:
            # Audio path: run the shared analysis core and render it in chat.
            os.environ.setdefault("WHISPER_MODEL", self.valves.WHISPER_MODEL)
            os.environ.setdefault("WHISPER_COMPUTE_TYPE", self.valves.WHISPER_COMPUTE_TYPE)
            try:
                result = run_analysis(match.group(0))
            except AnalysisError as e:
                return f"❌ {e.message}"
            return _format_markdown(result)

        # No audio URL → act as a normal assistant (also proves the Groq LLM backend).
        if not (user_message or "").strip():
            return ("Пришлите **ссылку на аудиофайл** звонка (wav/mp3/ogg) — верну анализ. "
                    "Прямую загрузку файла обслуживает REST `POST /analyze`.")
        return self._chat_groq(messages, body.get("stream", True))
