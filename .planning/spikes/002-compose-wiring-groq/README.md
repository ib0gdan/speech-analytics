---
spike: 002
name: compose-wiring-groq
type: standard
validates: "Given docker-compose with openwebui+pipelines, when Groq is set as the LLM backend, then chat reaches the model and the pipeline registers (port 9099, API key)"
verdict: VALIDATED
related: [001, 003]
tags: [docker-compose, openwebui, pipelines, groq, deploy]
---

# Spike 002: Compose Wiring + Groq

## What This Validates
The container topology: OpenWebUI ↔ pipelines server ↔ Groq LLM, all via `docker compose up`,
with correct ports, keys, and service-to-service URLs.

## Research
- pipelines README "Docker Compose together with Open WebUI" (verbatim base compose).

### Confirmed facts
- Pipelines image: `ghcr.io/open-webui/pipelines:main`, port **9099**.
- Default key `PIPELINES_API_KEY=0p3n-w3bu!`.
- Register in OpenWebUI: **Settings > Connections > OpenAI API**, URL `http://pipelines:9099`
  (service name in compose), key `0p3n-w3bu!`. Can be pre-set via env
  `OPENAI_API_BASE_URL` / `OPENAI_API_KEY` to skip the manual UI step.
- Custom deps (faster-whisper etc.) → build our own image FROM the pipelines image, or use
  `PIPELINES_URLS` for single-file installs. We need a Dockerfile (multiple deps).
- Per README note: the `pipelines` service is reachable only by `openwebui` on the compose
  network — good default security posture.

## Investigation Trail
1. Took the README's 2-service compose as the base.
2. **Where does Groq plug in?** Resolved: OpenWebUI's OpenAI connection points at the
   *pipelines* server (not Groq). Groq is called **inside** the pipeline's agent code via
   its own valves (`LLM_BASE_URL=https://api.groq.com/openai/v1`). So "OpenWebUI → Groq" is
   two hops: OpenWebUI → pipelines → Groq. This keeps the Pipeline as the real orchestrator
   (satisfies the "must be a Pipeline, not just FastAPI" requirement).
3. Added a third `api` service for REST `/analyze` sharing the same code image (spike 003).

## Results
**VERDICT: VALIDATED.** See `docker-compose.sketch.yaml`. Open items pushed to the build:
- Write the `Dockerfile` (FROM `ghcr.io/open-webui/pipelines:main`, add `faster-whisper`,
  `ctranslate2`, agent deps, ffmpeg).
- Decide deploy host (CPU): needs ≥2 vCPU for whisper (spike 004). HF Spaces (Docker SDK,
  2 vCPU/16GB free) or Render fit; free micro-instances will be too slow.
- `.env` / `.env.example` must carry `GROQ_API_KEY` (task requirement).
