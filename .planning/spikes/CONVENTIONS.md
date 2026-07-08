# Spike Conventions

Patterns and stack choices established across spike sessions. New spikes/build follow these
unless the question requires otherwise.

## Stack
- **Platform:** OpenWebUI + external Pipelines server (`ghcr.io/open-webui/pipelines:main`, port 9099).
- **Backend:** Python 3.11, FastAPI for REST `/analyze`.
- **ASR:** faster-whisper (CTranslate2), `int8`, default model `small`, built-in Silero VAD.
- **LLM:** Groq (OpenAI-compatible), `llama-3.3-70b-versatile`, via valves/`.env`.
- **Orchestration:** LangGraph or a Supervisor pattern over the 4 agents (decide in plan).
- **Containers:** docker-compose — services `openwebui`, `pipelines`, `api` from one image.

## Structure
- `pipeline.py` — thin OpenWebUI Pipeline; extracts audio URL, calls shared core, formats markdown.
- `analysis.py` — framework-agnostic `run_analysis(audio_source) -> dict` (single source of truth).
- `asr/` (transcriber, diarizer), `agents/` (classifier, quality, compliance, summarizer).
- `api/main.py` — FastAPI `POST /analyze`, imports the same `run_analysis`.
- Ports: OpenWebUI 3000→8080, pipelines 9099, api 8000.

## Patterns
- **Config via Valves + `.env`/`.env.example`** (both required by task). Never hardcode keys.
- **Audio in:** URL-in-chat-message (primary) / multipart to `/analyze` (direct upload).
- **Pipeline never owns logic** — it delegates to `run_analysis` so REST and chat stay in sync.
- **JSON structured logs** with each agent's input/output (task requirement).

## Tools & Libraries
- `faster-whisper`, `ctranslate2`, `ffmpeg` (system), `pydantic`, `fastapi`, `uvicorn`,
  `jiwer` (WER table), `openai` SDK pointed at Groq. `pyannote` — avoid unless stretch goal.
