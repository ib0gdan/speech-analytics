"""
VERIFIED skeleton for the MTBank OpenWebUI Pipeline (external pipelines server, port 9099).

Confirmed against open-webui/pipelines main README + examples + issue #164 (see README.md).
This is a REFERENCE skeleton produced during spike 001 — not the final implementation.

Key verified facts baked in:
- The external Pipelines server discovers a module-level `class Pipeline`.
- `pipe()` canonical signature: (self, user_message, model_id, messages, body).
- Uploaded chat files do NOT arrive as raw bytes in pipe(); they appear in
  `body["files"]` inside the async `inlet()` hook as {url, ...}, and OpenWebUI
  pre-parses documents to text. Binary audio is therefore NOT reliably delivered
  through chat upload. => PRIMARY audio path = URL pasted in the chat message.
- pipe() may return a str (rendered as chat markdown) or a generator (streaming).
"""

import re
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel


class Pipeline:
    class Valves(BaseModel):
        # OpenAI-compatible LLM backend for the 4 agents (Groq by default).
        LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
        LLM_API_KEY: str = ""
        LLM_MODEL: str = "llama-3.3-70b-versatile"
        # ASR
        WHISPER_MODEL: str = "small"          # small/base int8 for <60s on CPU; medium = valve
        WHISPER_COMPUTE_TYPE: str = "int8"
        # Where the ASR+agents live (the shared analysis service / in-process import)
        ANALYZE_TIMEOUT_S: int = 120

    def __init__(self):
        self.name = "MTBank Call Analytics"
        self.valves = self.Valves()
        self.transcriber = None
        self.agents = None

    async def on_startup(self):
        # Heavy init here (load whisper model, build agent graph) — runs once.
        # from asr.transcriber import Transcriber
        # self.transcriber = Transcriber(self.valves.WHISPER_MODEL, self.valves.WHISPER_COMPUTE_TYPE)
        # self.agents = build_agent_graph(self.valves)
        pass

    async def on_shutdown(self):
        pass

    def _extract_audio_url(self, user_message: str, messages: List[dict]) -> str | None:
        """Primary path: user pastes an audio URL in the chat message."""
        text = user_message or (messages[-1]["content"] if messages else "")
        m = re.search(r"https?://\S+\.(?:wav|mp3|ogg|m4a|flac)", text, re.IGNORECASE)
        return m.group(0) if m else None

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ) -> Union[str, Generator, Iterator]:
        audio_url = self._extract_audio_url(user_message, messages)
        if not audio_url:
            return (
                "Пришлите **ссылку на аудиофайл** (wav/mp3/ogg) в сообщении — "
                "я транскрибирую звонок и верну анализ.\n\n"
                "Прямую загрузку файла обслуживает REST `POST /analyze`."
            )

        # transcript = self.transcriber.run(audio_url)
        # results = self.agents.invoke(transcript)      # 4 agents via LangGraph/Supervisor
        # return format_markdown(results)               # rendered in the chat
        return f"(skeleton) got audio_url={audio_url}"
