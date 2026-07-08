"""
title: MTBank Call Analytics
author: ib0gdan
description: Phase-1 skeleton pipeline — proves OpenWebUI <-> Pipelines <-> Groq (LLM backend).
             Later phases add ASR (faster-whisper), Оператор/Клиент diarization, and the 4
             analysis agents behind the same pipe(). For now it forwards chat to Groq so we can
             verify the whole stack end-to-end.
requirements: requests
"""

import os
from typing import List, Union, Generator, Iterator

import requests
from pydantic import BaseModel


class Pipeline:
    class Valves(BaseModel):
        # All configurable live in OpenWebUI: Admin > Pipelines. Defaults come from env (.env).
        LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
        LLM_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    def __init__(self):
        self.name = "MTBank Call Analytics"
        self.valves = self.Valves()

    async def on_startup(self):
        status = "OK" if self.valves.LLM_API_KEY else "NO GROQ_API_KEY"
        print(f"[{self.name}] on_startup — model={self.valves.LLM_MODEL} key={status}")

    async def on_shutdown(self):
        print(f"[{self.name}] on_shutdown")

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Union[str, Generator, Iterator]:
        if not self.valves.LLM_API_KEY:
            return (
                "⚠️ GROQ_API_KEY не задан.\n\n"
                "Вставьте бесплатный ключ (https://console.groq.com) в файл `.env` "
                "(`GROQ_API_KEY=...`) и перезапустите: `docker compose up -d`."
            )

        headers = {
            "Authorization": f"Bearer {self.valves.LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        stream = body.get("stream", True)
        payload = {"model": self.valves.LLM_MODEL, "messages": messages, "stream": stream}

        try:
            resp = requests.post(
                f"{self.valves.LLM_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                stream=stream,
                timeout=60,
            )
            resp.raise_for_status()
            if stream:
                return resp.iter_lines()               # OpenWebUI renders the streamed chunks
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 — surface any backend error to the chat
            return f"Ошибка обращения к LLM ({self.valves.LLM_MODEL}): {e}"
