---
phase: quick-260710-nc0
plan: 01
subsystem: observability
status: complete
tags: [grafana, prometheus, metrics, bonus, docker-compose]
requires:
  - run_analysis (mtbank/analysis.py)
  - run_batch_analysis (mtbank/batch.py)
  - classifier topic whitelist (mtbank/agents/classifier.py)
provides:
  - mtbank.metrics (record_analysis, render, start_exporter)
  - "GET /metrics on api (:8000) and pipelines (:9100)"
  - profile-gated prometheus + grafana stack ("docker compose --profile metrics up -d --build")
  - deploy/grafana/dashboards/mtbank.json (provisioned "MTBank Call Analytics" dashboard)
affects:
  - mtbank/analysis.py
  - api/main.py
  - pipelines/mtbank_pipeline.py
  - Dockerfile.pipelines
  - api/requirements.txt
  - docker-compose.yml
  - README.md
tech-stack:
  added: ["prometheus-client==0.21.1", "prom/prometheus:v2.55.1", "grafana/grafana:11.4.0"]
  patterns:
    - "single instrumentation point in the shared core (run_analysis), not per-transport"
    - "two independent process registries scraped separately, summed in PromQL (design A)"
    - "graceful-optional import — observability can never sink the core audio->JSON path"
    - "Histogram (not Summary) for a cross-target-aggregatable quality_score distribution"
    - "opt-in via docker-compose profile, prod deploy untouched"
key-files:
  created:
    - mtbank/metrics.py
    - tests/test_metrics.py
    - deploy/prometheus/prometheus.yml
    - deploy/grafana/provisioning/datasources/datasource.yml
    - deploy/grafana/provisioning/dashboards/provider.yml
    - deploy/grafana/dashboards/mtbank.json
  modified:
    - mtbank/analysis.py
    - api/main.py
    - pipelines/mtbank_pipeline.py
    - api/requirements.txt
    - Dockerfile.pipelines
    - docker-compose.yml
    - README.md
decisions:
  - "record_analysis() called once, at the end of run_analysis — covers chat, REST, and batch"
  - "topic label clamped to the 5-value classifier whitelist, defence in depth (T-nc0-03)"
  - "quality_score and analysis_duration are Histograms (bucket counters sum across scrape targets); a Summary cannot be aggregated across independent processes"
  - "prometheus/grafana behind profiles: [\"metrics\"]; plain docker compose up -d and docker-compose.prod.yml both unchanged"
  - "prometheus_client import guarded — every metrics function is a safe no-op if the library is absent"
metrics:
  completed: 2026-07-10
  tasks: 4
  files-created: 6
  files-modified: 7
  full-suite-tests: 65
  measured-prometheus-grafana-ram-mib: 95.2
---

# Phase quick-260710-nc0 Plan 01: Grafana-дашборд над Prometheus-метриками (Bonus B) Summary

Prometheus metrics exposed by `api` (:8000) and `pipelines` (:9100), scraped by an opt-in
Prometheus + Grafana stack (`docker compose --profile metrics up -d --build`) that auto-provisions
a "MTBank Call Analytics" dashboard — количество звонков, топ тематик, quality_score (среднее +
распределение), доля нарушений комплаенса, p95 длительности анализа. One instrumentation point in
`run_analysis` covers chat, REST, and batch; because `pipelines` and `api` are separate processes
with separate registries, the true combined total only exists once Prometheus scrapes both targets
and the dashboard sums across them (`sum(...)`/`sum by (topic)(...)`).

## What was built

- **`mtbank/metrics.py`** — guarded `prometheus_client` import (`_ENABLED` flag; every public
  function becomes a no-op if the library is missing, so observability can never sink the core
  audio→JSON path, T-nc0-04). Module-level `Counter mtbank_calls_total`,
  `Counter mtbank_topic_total{topic}` (5-value whitelist, clamps unknowns to "другое"),
  `Counter mtbank_compliance_failed_total`, `Histogram mtbank_quality_score`
  (buckets 20/40/60/80/100), `Histogram mtbank_analysis_duration_seconds`
  (buckets 5/10/15/20/30/45/60/90/120). `record_analysis(result, duration_s)` reads the result
  dict defensively (`.get`) and never mutates it; `render()` returns the exposition bytes;
  `start_exporter(port)` wraps `start_http_server`.
- **`mtbank/analysis.py`** — one call, `metrics.record_analysis(result, result["elapsed_s"])`,
  immediately before `return result` in `run_analysis`. Single point that covers chat, REST, and
  `run_batch_analysis` (which calls `run_analysis` per source).
- **`api/main.py`** — `GET /metrics` (scrape target #1, the REST registry).
- **`pipelines/mtbank_pipeline.py`** — `on_startup` starts `metrics.start_exporter(9100)` (scrape
  target #2, the chat registry) in its own try/except, mirroring the existing whisper-warmup
  guard so a port clash or reload-triggered `OSError` never blocks chat startup. Pipeline
  frontmatter `requirements:` line left untouched (grabli #2).
- **`api/requirements.txt` / `Dockerfile.pipelines`** — `prometheus-client==0.21.1` pinned in
  both (api + test env via the api container; pipelines baked into the image, not the frontmatter
  requirements line).
- **`docker-compose.yml`** — `prometheus` (`prom/prometheus:v2.55.1`, `mtbank-prometheus`, host
  `9090`) and `grafana` (`grafana/grafana:11.4.0`, `mtbank-grafana`, host `3001`, anonymous
  Viewer), both `profiles: ["metrics"]`, named volumes `prometheus-data`/`grafana-data`.
  `docker-compose.prod.yml` was NOT touched.
- **`deploy/prometheus/prometheus.yml`** — two static scrape jobs, `mtbank-api` → `api:8000`,
  `mtbank-pipelines` → `pipelines:9100`, 15s interval.
- **`deploy/grafana/provisioning/`** — fixed-uid (`prometheus`) datasource + a file dashboard
  provider pointing at `/var/lib/grafana/dashboards`, so `mtbank.json` loads on startup with zero
  manual clicking.
- **`deploy/grafana/dashboards/mtbank.json`** — 6 panels, every target `sum(...)`/`sum by(...)`
  across both scrape targets: stat "Количество звонков (чат + REST)", stat "Средний
  quality_score", stat "Доля нарушений комплаенса" (percentunit), piechart "Топ тематик",
  barchart "Распределение quality_score" (`sum by (le)`), timeseries "p95 длительности анализа,
  с" (`histogram_quantile`). `refresh: "10s"`, stable `uid: mtbank-call-analytics`.
- **`tests/test_metrics.py`** (4 tests, delta-based against the process-global default
  `REGISTRY`): `run_analysis` +1 `mtbank_calls_total` and +1 `mtbank_topic_total{topic="кредиты"}`;
  `run_batch_analysis` over 2 sources +2 `mtbank_calls_total` (design F, proven — the trends agent
  itself never calls `run_analysis`); a compliance-failed FakeLLM response +1
  `mtbank_compliance_failed_total`; `GET /metrics` returns 200, `text/plain; ...version=0.0.4...`,
  body contains `mtbank_calls_total`.
- **`README.md`** — new `## Метрики и дашборд (Grafana)` section (metrics table, WHY the
  instrumentation point lives in `run_analysis`, the honest two-scrape-targets design, the one
  bring-up command, MEASURED before/after counter values); test count refreshed to 65 in three
  places; Grafana removed from the "Бонусные задания … не реализованы" line (only real-time
  WebSocket remains listed as not implemented).

## Known trap verified empirically (before writing assertions)

`prometheus_client.Counter("mtbank_calls_total", ...)` was checked with a throwaway counter
inside the running api container: `REGISTRY.get_sample_value('mtbank_calls_total')` returns the
value; `REGISTRY.get_sample_value('mtbank_calls')` (without `_total`) returns `None`. The library
strips the trailing `_total` from the metric name internally but the exposed **sample** name keeps
it — confirmed live, not assumed, before `tests/test_metrics.py` and the dashboard PromQL were
written against that name.

## Measured results (real commands, live stack)

- **Full suite:** `docker compose exec -T api pytest` → **65 passed in ~5 s** (61 baseline + 4 new
  `tests/test_metrics.py`). `tests/test_api.py` (REST contract) stayed green — `/analyze` and
  `/analyze-batch` response shapes are unchanged.
- **`docker compose exec -T api sh -c "... urlopen('http://localhost:8000/metrics') ..."`** and
  **`docker compose exec -T pipelines sh -c "... urlopen('http://localhost:9100/metrics') ..."`**
  — both processes serve the Prometheus text-exposition format and both bodies contain
  `mtbank_calls_total`.
- **`docker compose --profile metrics up -d --build`** brought up `mtbank-prometheus` +
  `mtbank-grafana` alongside the existing five services.
- **Prometheus targets** (`/api/v1/targets`): `[('mtbank-api', 'up'), ('mtbank-pipelines', 'up')]`
  — both healthy.
- **Grafana:** `GET /api/health` → `200` anonymously; `GET /api/search?query=MTBank` lists
  `{"uid":"mtbank-call-analytics","title":"MTBank Call Analytics", ...}` — provisioned with zero
  manual clicking.
- **`docker compose config --services`** (no profile) lists only
  `api, files, pipelines, openwebui, proxy` — `prometheus`/`grafana` are absent from the plain
  compose invocation, confirming the opt-in profile gate. `docker compose --profile metrics
  config --services` adds `prometheus, grafana`. A subsequent plain `docker compose up -d` while
  the metrics containers were already running left them untouched (didn't stop or recreate them,
  and didn't start them from a clean state either).
- **True dual-path proof — the core deliverable of this task:**
  1. `sum(mtbank_calls_total)` before any live call: **`0`**.
  2. A REST call, `POST /analyze` with `call_dialog.mp3` (elapsed 6.72s) → `sum(mtbank_calls_total)`
     went **`0 → 1`**, entirely on the `mtbank-api` target
     (`mtbank_calls_total{job="mtbank-api"}=1`, `{job="mtbank-pipelines"}=0`).
  3. A real chat message through the live pipelines server (`POST :9099/chat/completions`,
     `Authorization: Bearer 0p3n-w3bu!`, model `mtbank_pipeline` from `GET /models`,
     `stream:false`) with `call_card_blocked.mp3` (pipeline-reported 13.23s) →
     `sum(mtbank_calls_total)` went **`1 → 2`**, the increment landing entirely on the
     `mtbank-pipelines` target (`{job="mtbank-pipelines"}=1`). This is the design's whole point:
     the chat path — the primary graded interface — is fully counted, and only visible as the
     true total once Prometheus sums both targets.
  4. `sum by (topic) (mtbank_topic_total)` after both calls: `{topic="другое"}=2` — non-zero,
     confirming the "Топ тематик" panel would render populated, not empty.
- **Measured prometheus+grafana RAM:** `docker stats --no-stream mtbank-prometheus mtbank-grafana`
  → `mtbank-prometheus 22.82 MiB`, `mtbank-grafana 72.35 MiB` → **~95 MiB combined**, well under
  the HANDOFF's unmeasured "~350 MiB" guess (replaced in README with this real number). Measured
  right after container start with only a few scrapes/dashboard loads — not a steady-state ceiling
  under sustained load, noted as a measurement-condition caveat, not a claim of a hard cap.
- Default (no-profile) stack RAM was NOT re-measured in this task — README states it is unchanged
  at the prior ~2.3 GiB figure from the trends-task HANDOFF; the profile-gate structurally
  guarantees `prometheus`/`grafana` never run in that configuration (confirmed above via
  `docker compose config --services`), so re-measuring the untouched services was not necessary
  to support that claim.

## Could not fully verify (documented honestly)

- **quality_score panel with real, non-degraded numbers.** During the live dual-path proof above,
  the real Groq API (`llama-3.3-70b-versatile`) returned `429 Too Many Requests` on two follow-up
  `/analyze` calls I made purely to get a nicer `quality_score` reading for the dashboard —
  the free tier was exhausted by the volume of live testing done across this task and the sibling
  trends task earlier today. Both calls degraded correctly (`agent_errors` populated,
  `quality_score.total=0`, `classification.topic="другое"`), which is itself a correct exercise of
  the existing agent-fallback resilience, and `mtbank_quality_score_count` still incremented (with
  a `0` observation) — so the histogram metric mechanism is proven end-to-end, but I did not
  observe a screenshot-worthy non-zero `mtbank_quality_score_sum`. This is a real external rate
  limit, not a bug in the metrics/dashboard code; a reviewer running the demo with a fresh Groq
  quota will see populated, meaningful quality-score panels.
- I did not open Grafana in a browser to visually confirm panel rendering (only its HTTP API:
  `/api/health` 200, `/api/search` lists the dashboard). The dashboard JSON was validated as valid
  JSON and matches Grafana's documented schema for the pinned 11.4.0 version, but rendering was
  not screenshotted.

## Deviations from Plan

None — plan executed exactly as written. All four tasks' `<action>` and `<verify>` steps completed
without needing a Rule 1-4 deviation.

## Threat mitigations verified

- **T-nc0-01** (Information Disclosure, `/metrics`): confirmed the exposed metrics are aggregate
  counters only — no `request_id`/`url`/`filename` labels anywhere in `mtbank/metrics.py`.
- **T-nc0-02** (Grafana anonymous Viewer): `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer` in
  `docker-compose.yml`; `/api/health` answered 200 with no admin surface exercised.
- **T-nc0-03** (unbounded label cardinality): `_TOPICS` whitelist in `mtbank/metrics.py` clamps
  any unexpected topic to "другое" before labelling.
- **T-nc0-04** (prometheus_client absent breaks core): `_ENABLED` guard verified by inspection —
  every `record_*`/`render`/`start_exporter` call is gated; the full suite (which imports
  `mtbank.metrics` in every test run) stayed green throughout, and the guard was never actually
  exercised live (the dependency was always present), so this is a code-inspection verification,
  not a live "pull the dependency and re-run" test.
- **T-nc0-SC** (pip install prometheus-client): pinned `0.21.1` in both `api/requirements.txt` and
  `Dockerfile.pipelines`; NOT added to the pipeline frontmatter `requirements:` line (verified by
  reading `pipelines/mtbank_pipeline.py` after the edit — line 12 is still the bare `requests`).

## Commits

| Hash | Message |
| ---- | ------- |
| `a0779ba` | feat(metrics): add Prometheus metrics module + single instrumentation point in run_analysis |
| `7eb9012` | feat(metrics): expose /metrics on api and pipelines processes |
| `9871ac0` | feat(grafana): profile-gated Prometheus + Grafana with self-provisioning dashboard |
| `d61f0ca` | docs: document the Grafana/Prometheus stack and refresh the measured test count |

All commits authored by `ib0gdan`, no Claude/Anthropic attribution trailer.

## Self-Check: PASSED

- Files exist: `mtbank/metrics.py`, `tests/test_metrics.py`, `deploy/prometheus/prometheus.yml`,
  `deploy/grafana/provisioning/datasources/datasource.yml`,
  `deploy/grafana/provisioning/dashboards/provider.yml`, `deploy/grafana/dashboards/mtbank.json`
  — all FOUND.
- Commits exist: `a0779ba`, `7eb9012`, `9871ac0`, `d61f0ca` — all present in `git log`.
- Full suite: 65 passed.
