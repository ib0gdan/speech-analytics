# Phase 1: Deployed Skeleton (End-to-End Vertical Slice) - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a THIN end-to-end vertical slice, deployed live over HTTPS on a free CPU host:
a stubbed `audio → JSON` path reachable BOTH through the OpenWebUI chat (URL in message)
and through REST `POST /analyze`, proving that docker-compose + a real OpenWebUI Pipeline +
the shared `run_analysis()` core all work together on day 1. Content is stubbed; the plumbing,
the response contract, and the deployment are real.

Covers: INFRA-01, INFRA-02, INFRA-03, INFRA-04, CORE-01, API-01, UI-01.
NOT this phase: real ASR (Phase 2), real agents (Phase 3), tests suite (Phase 4), <60s perf
verification + WER + README (Phase 5).

**Note on user role:** User delegated all infra/deployment gray areas to Claude ("сделать
бесплатно, дай конкретную инструкцию"). Decisions below are Claude's, optimized for free-tier +
minimal user effort. See [[user-profile-infra]].
</domain>

<decisions>
## Implementation Decisions

### Demo hosting (the crux)
- **D-01 (REVISED 2026-07-08):** Live demo host = **DigitalOcean droplet** (Ubuntu, 4 GB RAM),
  running the REAL `docker-compose.prod.yml` (openwebui + pipelines + api + Caddy). Free for the
  hiring window via DO's **$200 / 60-day new-account credit**. HTTPS via **Caddy auto-TLS** using
  a **`<ip>.sslip.io`** hostname (no domain purchase).
  - **Why revised:** the original plan was HF Spaces (Docker SDK) but **HF moved Docker/Gradio
    Spaces behind a PAID PRO plan** (only Static Spaces are free now — no compute) — discovered
    when creating the Space. Static can't run OpenWebUI/pipelines/whisper, so HF is out.
  - Rejected: Render/Railway free (≤512 MB — OpenWebUI needs ~1.5–2 GB), Oracle Always Free
    (24 GB, forever-free, but signup friction). DO chosen: it's on the task's FAQ list, easy
    signup, free via credit, always-on (no cold starts), runs the faithful compose.
- **D-02 (REVISED):** No more single-container all-in-one gymnastics — the droplet runs the real
  multi-service compose (same services as local dev). Caddy is the only public-facing service
  (ports 80/443); it routes `/analyze` `/health` `/docs` `/openapi.json` → FastAPI and everything
  else → OpenWebUI. pipelines stays internal. The HF all-in-one image (`deploy/hf/`) is kept as a
  documented fallback but not used. Deploy = create droplet → run one setup script.

### Local vs demo parity
- **D-03:** Keep BOTH: (a) `docker-compose.yml` with the three real services (openwebui +
  pipelines + api) for local dev — this satisfies INFRA-01 "`docker compose up` поднимает весь
  стек"; (b) the all-in-one `Dockerfile` (+ `supervisord.conf` + `Caddyfile`) for the HF Spaces
  demo. Both build from the SAME source modules (`asr/`, `agents/`, `analysis.py`, `pipeline.py`,
  `api/`). No logic divergence — only packaging differs. Document both in README.

### Skeleton fidelity (contract-first)
- **D-04:** Phase 1 fixes the FULL target JSON response schema immediately (transcript,
  classification, quality_score{total,checklist}, compliance{passed,issues}, summary,
  action_items) — returned with obvious **stub/placeholder values**. Locking the contract on day 1
  lets Phases 2–3 fill it in without changing interfaces.
- **D-05:** Stub internals: a hardcoded 2–3 segment transcript; a single trivial "analysis" step
  (e.g. keyword topic guess or a fixed classification) — NOT the 4 real agents. The real chat
  plumbing (OpenWebUI → pipelines `pipe()` → `run_analysis()` → markdown) and the REST path must
  genuinely work end-to-end.
- **D-06:** Audio input in Phase 1 = **URL in the chat message** (primary path) and multipart/`{url}`
  to `/analyze`. The stub may skip real downloading, but the plumbing that extracts the URL /
  receives the file must be real so Phase 2 only swaps the transcriber.

### Config, secrets, logging
- **D-07:** `.env` + `.env.example` from day 1 (`GROQ_API_KEY`, `PIPELINES_API_KEY`, `LLM_MODEL`,
  `WHISPER_MODEL`). Secrets never hardcoded; on HF Spaces they go in Space **Secrets** (env), not
  in git. (`.gitignore` already excludes `.env`.)
- **D-08:** Structured **JSON logging** scaffolded now (one log line per stage with input/output),
  so when real agents arrive in Phase 3 they just plug into the existing logger (INFRA-04).

### Skeleton verification
- **D-09:** Keep Phase 1 light: add a `GET /health` endpoint + one trivial smoke check that
  `POST /analyze` returns 200 with all required JSON keys. Full pytest suite is Phase 4 — do NOT
  build it here.

### Claude's Discretion
- Reverse proxy choice (Caddy vs nginx), supervisor choice (supervisord vs a shell wrapper),
  exact Python project layout, base images — Claude decides during planning, guided by spike
  CONVENTIONS.md.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Verified architecture (spike — highest authority)
- `.planning/spikes/MANIFEST.md` — locked requirements + the one open risk (diarizer/timing, Phase 2)
- `.planning/spikes/CONVENTIONS.md` — verified stack, structure, ports, patterns
- `.planning/spikes/001-pipeline-interface-audio/README.md` — exact `pipe()` interface; audio-via-URL decision
- `.planning/spikes/001-pipeline-interface-audio/pipeline_skeleton.py` — verified Pipeline skeleton to build from
- `.planning/spikes/002-compose-wiring-groq/README.md` + `docker-compose.sketch.yaml` — compose topology, Groq wiring
- `.planning/spikes/003-fastapi-coexist/README.md` — shared-core `run_analysis()` pattern (Pipeline + REST)

### Project
- `.planning/PROJECT.md` — constraints, key decisions, out-of-scope
- `.planning/REQUIREMENTS.md` — REQ-IDs for this phase (INFRA-01..04, CORE-01, API-01, UI-01)
- `README.md` (repo root) — the task spec: exact JSON response schema, tech-stack requirements, disqualifiers

### External docs (research should confirm current APIs)
- OpenWebUI Pipelines: https://github.com/open-webui/pipelines (README — docker, :9099, key `0p3n-w3bu!`)
- Hugging Face Spaces Docker SDK: https://huggingface.co/docs/hub/spaces-sdks-docker (port 7860, Secrets, persistence)
- Groq OpenAI-compatible API: https://console.groq.com/docs (base_url `https://api.groq.com/openai/v1`)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.planning/spikes/001-pipeline-interface-audio/pipeline_skeleton.py` — verified `Pipeline` class
  (Valves, on_startup, `pipe(user_message, model_id, messages, body)`, URL extraction) — start here.
- `.planning/spikes/002-compose-wiring-groq/docker-compose.sketch.yaml` — base for the local `docker-compose.yml`.

### Established Patterns
- Shared framework-agnostic `run_analysis(audio_source) -> dict` (spike 003) is the single source
  of truth; both `pipeline.py` and `api/main.py` import it. Enforce this from Phase 1.
- Valves + `.env` for all config; JSON logs per stage.

### Integration Points
- OpenWebUI (Connections → OpenAI API) → `http://pipelines:9099` (local) / internal (demo).
- pipeline `pipe()` and FastAPI `/analyze` both call `run_analysis()`.
</code_context>

<specifics>
## Specific Ideas

- Contract-first: the stub must already emit the EXACT JSON shape from the task README example,
  so nothing downstream has to change the interface.
- Demo must show the OpenWebUI chat (task requires it), not just the REST endpoint.

## User Action Items (external, free — only the user can do these)
1. **Groq API key** — sign up free at console.groq.com → create an API key (for the agents' LLM).
2. **Hugging Face account + a new Space** — huggingface.co → New Space → SDK: **Docker** → free.
   (Claude provides the exact files + push steps during execution; user just needs the account.)
These are the only things Claude cannot do; everything else is code Claude writes.
</specifics>

<deferred>
## Deferred Ideas
- Real ASR + diarization → Phase 2.
- Real 4 agents + orchestration → Phase 3.
- pytest unit + integration suite → Phase 4.
- <60s/5min perf verification, WER table, Russian solution-README, final demo sign-off → Phase 5.
- Bonuses (WebSocket real-time, Grafana, trends agent) → out of v1 scope.
- If HF Spaces all-in-one proves too heavy/slow at demo time, fallback = cheap VPS running the
  real docker-compose (noted, not chosen).
</deferred>

---

*Phase: 1-Deployed Skeleton (End-to-End Vertical Slice)*
*Context gathered: 2026-07-08*
