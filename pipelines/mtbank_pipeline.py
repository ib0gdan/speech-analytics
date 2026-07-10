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

from mtbank import metrics
from mtbank.analysis import run_analysis  # shared core, mounted at /app/mtbank
from mtbank.batch import run_batch_analysis
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


def _format_trends_markdown(batch_result: dict) -> str:
    """Render run_batch_analysis()'s output as chat markdown (BONUS-A-TRENDS).

    Same split as the single-call report: everything under "Агрегаты" is code-computed
    (mtbank.agents.trends.compute_aggregates), the rest is the LLM's judgement.
    """
    t = batch_result.get("trends", {})
    header = f"## 📊 Тренды по {t.get('num_calls', 0)} звонкам"
    if batch_result.get("elapsed_s") is not None:
        header += f" _(обработка {batch_result['elapsed_s']} с)_"
    lines = [header]

    topics = t.get("topics", {})
    topics_str = " · ".join(f"{topic}: {n}" for topic, n in topics.items()) or "нет данных"
    lines.append(f"\n### Темы обращений\n- {topics_str}")

    q = t.get("quality", {})
    lines.append(
        f"\n### Качество обслуживания\n"
        f"- Среднее: **{q.get('avg')}** · Мин: **{q.get('min')}** · Макс: **{q.get('max')}**"
    )

    pass_rate = t.get("checklist_pass_rate", {})
    if pass_rate:
        checks = " · ".join(
            f"{_CHECKLIST_RU.get(k, k)}: {round(v * 100)}%" for k, v in pass_rate.items()
        )
        lines.append(f"\n### Выполнение чеклиста по звонкам\n- {checks}")

    failure_rate = t.get("compliance_failure_rate", 0.0)
    lines.append(f"\n### Комплаенс\n- Доля звонков с нарушениями: **{round(failure_rate * 100)}%**")
    hits = t.get("forbidden_phrase_hits", {})
    if hits:
        hits_str = "\n".join(f"  - {phrase}: {n}" for phrase, n in hits.items())
        lines.append(f"- Частота запрещённых фраз:\n{hits_str}")

    patterns = t.get("patterns", [])
    if patterns:
        lines.append("\n### Паттерны\n" + "\n".join(f"- {p}" for p in patterns))
    causes = t.get("causes", [])
    if causes:
        lines.append("\n### Вероятные причины\n" + "\n".join(f"- {c}" for c in causes))
    recommendations = t.get("recommendations", [])
    if recommendations:
        lines.append("\n### Рекомендации\n" + "\n".join(f"- {r}" for r in recommendations))
    grouped_items = t.get("grouped_action_items", [])
    if grouped_items:
        lines.append("\n### Сгруппированные задачи\n" + "\n".join(f"- {a}" for a in grouped_items))
    grouped_issues = t.get("grouped_compliance_issues", [])
    if grouped_issues:
        lines.append(
            "\n### Сгруппированные нарушения комплаенса\n"
            + "\n".join(f"- {i}" for i in grouped_issues)
        )

    calls = batch_result.get("calls", [])
    if calls:
        call_lines = []
        for call in calls:
            c = call.get("classification", {})
            q_total = call.get("quality_score", {}).get("total")
            comp_passed = call.get("compliance", {}).get("passed", True)
            call_lines.append(
                f"- {c.get('topic', 'другое')} · качество {q_total} · "
                f"комплаенс {'✅' if comp_passed else '❌'}"
            )
        lines.append("\n### Звонки\n" + "\n".join(call_lines))

    errors = batch_result.get("errors", [])
    if errors:
        err_str = "; ".join(f"{e.get('source')}: {e.get('message')}" for e in errors)
        lines.append(f"\n> ⚠️ Не удалось проанализировать {len(errors)} источник(ов): {err_str}")

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

        # Prometheus scrape target #2 — the chat path's registry lives in THIS process, and
        # OpenWebUI's own FastAPI app exposes no route we can hook, so we start a tiny
        # in-process exporter instead. Same guard style as the warmup above: a port clash or
        # exporter failure (e.g. the pipelines server reloading this module twice) must never
        # block the chat.
        try:
            metrics.start_exporter(int(os.getenv("METRICS_PORT", "9100")))
            print(f"[{self.name}] metrics exporter started on :9100")
        except Exception as e:  # noqa: BLE001
            print(f"[{self.name}] metrics exporter failed: {e}")

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
        # Dedupe preserving order — a URL pasted twice by accident is still a single-call message.
        urls = list(dict.fromkeys(_AUDIO_URL_RE.findall(user_message or "")))

        if len(urls) > 1:
            # Batch path: >1 distinct audio URL -> run_batch_analysis + trends report.
            os.environ.setdefault("WHISPER_MODEL", self.valves.WHISPER_MODEL)
            os.environ.setdefault("WHISPER_COMPUTE_TYPE", self.valves.WHISPER_COMPUTE_TYPE)
            try:
                batch_result = run_batch_analysis(urls)
            except AnalysisError as e:
                return f"❌ {e.message}"
            return _format_trends_markdown(batch_result)

        if len(urls) == 1:
            # Single-call path: UNCHANGED behaviour.
            os.environ.setdefault("WHISPER_MODEL", self.valves.WHISPER_MODEL)
            os.environ.setdefault("WHISPER_COMPUTE_TYPE", self.valves.WHISPER_COMPUTE_TYPE)
            try:
                result = run_analysis(urls[0])
            except AnalysisError as e:
                return f"❌ {e.message}"
            return _format_markdown(result)

        # No audio URL → act as a normal assistant (also proves the Groq LLM backend).
        if not (user_message or "").strip():
            return ("Пришлите **ссылку на аудиофайл** звонка (wav/mp3/ogg) — верну анализ. "
                    "Прямую загрузку файла обслуживает REST `POST /analyze`.")
        return self._chat_groq(messages, body.get("stream", True))
