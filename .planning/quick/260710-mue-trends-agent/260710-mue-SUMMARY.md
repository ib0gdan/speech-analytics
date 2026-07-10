---
phase: quick-260710-mue
plan: 01
subsystem: analytics
status: complete
tags: [trends, batch, bonus, llm, openwebui, fastapi]
requires:
  - run_analysis (mtbank/analysis.py)
  - compliance.check_forbidden (mtbank/agents/compliance.py)
  - FakeLLM (tests/conftest.py)
provides:
  - mtbank.agents.trends (compute_aggregates, run, fallback)
  - mtbank.batch.run_batch_analysis
  - "POST /analyze-batch"
  - chat batch mode (pipelines/mtbank_pipeline.py)
affects:
  - api/main.py
  - pipelines/mtbank_pipeline.py
  - README.md
tech-stack:
  added: []
  patterns:
    - "deterministic aggregates in code + LLM for judgement only (mirrors quality.compute_total)"
    - "sequential inter-call batch, parallel intra-call agents"
    - "per-source try/except so one failure never sinks the batch"
key-files:
  created:
    - mtbank/agents/trends.py
    - mtbank/batch.py
    - tests/test_trends.py
  modified:
    - tests/conftest.py
    - api/main.py
    - pipelines/mtbank_pipeline.py
    - tests/test_api.py
    - README.md
decisions:
  - "compute_aggregates() is pure code; the LLM never contributes numbers"
  - "forbidden_phrase_hits reuses compliance.check_forbidden — single source of truth"
  - "LLM failure keeps aggregates, degrades only judgement fields to empty lists"
  - "batch runs calls sequentially to bound CPU/RAM on the 2-vCPU target host"
  - "MAX_BATCH_SOURCES=20 caps the amplified fetch/CPU/SSRF surface (T-mue-01)"
  - "chat batch branch keys off >1 UNIQUE audio URL; single-URL path untouched"
metrics:
  completed: 2026-07-10
  tasks: 4
  files-created: 3
  files-modified: 5
  full-suite-tests: 61
  live-batch-2call-elapsed-s: 18.12
---

# Phase quick-260710-mue Plan 01: Агент трендов (Bonus A) Summary

Fifth LLM agent that analyzes MULTIPLE calls: `compute_aggregates()` computes topic distribution,
quality avg/min/max, per-checklist pass rates, compliance failure rate, and forbidden-phrase
frequency entirely IN CODE, while the LLM contributes only judgement (patterns, causes,
recommendations, and semantically grouped action items / compliance issues). Exposed via REST
`POST /analyze-batch` and a chat batch branch that fires on >1 distinct audio URL.

## What was built

- **`mtbank/agents/trends.py`** — `NAME`, `SYSTEM`, `compute_aggregates`, `run`, `fallback`,
  plus `_empty_aggregates`/`_empty_judgement`/`_coerce_str_list` helpers. `run` computes
  aggregates first, returns safe empties without an LLM call on an empty batch, and wraps the
  single LLM call in try/except so aggregates survive any model failure. Judgement fields are
  strictly coerced (non-list → `[]`; ints/None/blank dropped; capped at 10).
- **`mtbank/batch.py`** — `run_batch_analysis(sources, *, llm, request_id)` reuses `run_analysis`
  sequentially, isolates each source in try/except (`AnalysisError` and a broad guard) into
  `errors`, computes trends over the successes, and returns
  `{calls, errors, trends, request_id, elapsed_s}`. `MAX_BATCH_SOURCES = 20` → `batch_too_large`.
- **`api/main.py`** — `POST /analyze-batch` accepts JSON `{urls:[...]}` or multipart `files`+`urls`,
  maps `AnalysisError` (incl. `batch_too_large`) to HTTP 400. `/analyze` and its keys untouched.
- **`pipelines/mtbank_pipeline.py`** — `pipe()` dedupes audio URLs; >1 → `run_batch_analysis` +
  new `_format_trends_markdown` (Russian report); exactly 1 → the original single-call path,
  byte-for-byte unchanged; 0 → existing assistant/empty paths. The `requirements:` frontmatter
  line was NOT touched.
- **Tests** — `tests/test_trends.py` (15 tests: aggregates over 3 calls, forbidden-phrase reuse,
  empty/single-call, degraded-call safety, empty-batch no-LLM, judgement merge, LLM-failure
  degradation, garbage coercion, fallback shape, NAME, batch resilience with one failure, all-fail
  batch, and MAX_BATCH_SOURCES). `tests/conftest.py` gained a `"trends"` DEFAULT_RESPONSES entry;
  `tests/test_api.py` gained the `/analyze-batch` happy path + empty-body rejection.

## TDD gates

- **RED** `e2febf3` — `test(trends): ...` committed with the failing suite (ImportError: no
  `mtbank.batch`); the pre-existing 44 stayed green.
- **GREEN** `671cb29` — `feat(trends): ...` implemented the agent + batch core; all 17 collected
  trends tests pass (15 unique + parametrisation), fast subset green.

## Measured results (real commands, warm model)

- **Full suite:** `docker compose exec -T api pytest -q` → **61 passed in ~4.6–5.0 s** (44 baseline
  + test_api 6→8 + test_trends 15). Per-file (collect-only): agents 22, pipeline 9, diarizer 7,
  api 8, trends 15.
- **Live REST batch of 2** (`call_card_blocked.mp3` + `call_credit_consultation.wav`):
  `calls`=2, `errors`=[], `trends.num_calls`=2, `topics`={карты:1, кредиты:1},
  `quality`={avg:100.0, min:100, max:100}, real Groq patterns/recommendations in Russian.
  **`elapsed_s` = 18.12.**
- **Live REST batch resilience** (`call_dialog.mp3` + a 404 url): `calls`=1, `errors`=1 with
  `code="audio_fetch_error"`, `trends.num_calls`=1 — decision 6 proven on the live stack.
- **Live chat, 2 URLs** via the real pipelines server (`:9099`, model `mtbank_pipeline`,
  `stream:false`): rendered the Russian trends report ("## 📊 Тренды по 2 звонкам", topic
  distribution, quality aggregates, LLM patterns/causes/recommendations, grouped items) — not a
  single-call report. Chat batch processing time reported by the pipeline: 20.93 s.
- **Live chat regression, 1 URL** (`call_dialog.mp3`): rendered the ORIGINAL single-call layout
  ("## 📞 Анализ звонка", Транскрипт, Классификация, Качество обслуживания, Комплаенс, Резюме,
  Задачи после звонка) — unchanged.

`GROQ_API_KEY` was confirmed SET in both `api` and `pipelines` containers (len 56), and whisper
was preloaded (`whisper_preloaded` in the api logs) before the live checks ran.

## Deviations from Plan

None — plan executed exactly as written. No auto-fixes were required; all four live checks passed
on the first run after container recreation.

## Threat mitigations verified

- **T-mue-01** (batch DoS): `MAX_BATCH_SOURCES=20` → `batch_too_large` (unit test
  `test_run_batch_analysis_enforces_max_sources`); sequential execution bounds peak CPU/RAM.
- **T-mue-02** (one poisoned source): per-call try/except (live 404 test + monkeypatch tests).
- **T-mue-03** (error surface): `/analyze-batch` reuses the safe `AnalysisError.message`+`code`
  mapping; the `errors` list carries only a safe `_source_repr` (never raw bytes).

## Commits

| Hash | Message |
| ---- | ------- |
| `e2febf3` | test(trends): add failing tests for aggregates, LLM judgement, and batch resilience |
| `671cb29` | feat(trends): implement 📊 trends agent and run_batch_analysis |
| `912c7fc` | feat(api): expose trends via POST /analyze-batch and chat batch mode |
| `e99ee90` | docs: document the trends agent, /analyze-batch, and measured test count |

All commits authored by `ib0gdan`, verified free of any Claude/Anthropic attribution trailer.

## Could not verify

Nothing was left unverified. All automated tests, all four live end-to-end checks (REST batch,
REST 404 resilience, chat trends report, chat single-call regression), and the README
consistency checks ran successfully against the real stack.

## Self-Check: PASSED

- Files exist: `mtbank/agents/trends.py`, `mtbank/batch.py`, `tests/test_trends.py` — all FOUND.
- Commits exist: `e2febf3`, `671cb29`, `912c7fc`, `e99ee90` — all present in `git log`.
- Full suite: 61 passed.
