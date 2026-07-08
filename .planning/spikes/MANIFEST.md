# Spike Manifest

## Idea
Feasibility of the MTBank AI-Engineer test task: a contact-center call-analytics prototype —
faster-whisper ASR + Оператор/Клиент diarization → 4 LLM agents (classifier, quality,
compliance, summarizer) orchestrated via an **OpenWebUI Pipeline**, exposed through the
OpenWebUI chat AND a REST `POST /analyze`, shipped with docker-compose, tests, JSON logs, and
a live HTTPS demo. Constraints: CPU-only host, external LLM via Groq, response < 60s for a
5-min file. This spike verifies the unknown/risky pieces from official docs before roadmapping.

## Requirements
Non-negotiable decisions that emerged and must hold in the real build:
- **Use OpenWebUI Pipelines (external server, port 9099)** — mandatory per task; justified
  because our whisper+multi-agent workload is the "heavy compute offloaded from main instance"
  case the maintainers endorse even while discouraging Pipelines for simple uses.
- **Primary audio input = URL pasted in the chat message** (raw chat file-upload of binary
  audio is not reliably delivered to `pipe()`); **direct file upload served by REST /analyze**.
- **Shared framework-agnostic core** `run_analysis(audio) -> dict` imported by BOTH the
  Pipeline and the FastAPI service — no duplicated ASR/agent logic.
- **Groq** as the OpenAI-compatible LLM backend, configured via Valves/`.env`.
- **Default `WHISPER_MODEL=small`, `compute_type=int8`**, built-in VAD; `medium` opt-in only.
- **Deploy host must have ≥2 vCPU** (free micro-instances too slow for <60s).

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | pipeline-interface-audio | standard | Exact Pipeline/Valves/pipe interface + how audio reaches pipe() | ✅ VALIDATED | openwebui, pipelines, asr, audio-ingestion |
| 002 | compose-wiring-groq | standard | openwebui+pipelines+Groq topology via docker compose | ✅ VALIDATED | docker-compose, groq, deploy |
| 003 | fastapi-coexist | standard | REST /analyze coexists with Pipeline, shares logic | ✅ VALIDATED | fastapi, rest, architecture |
| 004 | whisper-cpu-diarization | standard | faster-whisper <60s on CPU + light diarization no pyannote | ⚠️ PARTIAL | asr, faster-whisper, cpu, diarization |

## Signal for the Build
- Architecture is confirmed and de-risked; roadmap can be built on it.
- **One genuinely open risk** → validate empirically during build: the no-pyannote 2-speaker
  diarizer on a real RU phone dialog, and real transcription time on the chosen ≥2-vCPU host.
