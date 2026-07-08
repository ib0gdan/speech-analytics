---
spike: 003
name: fastapi-coexist
type: standard
validates: "Given the pipelines server, when we add REST POST /analyze, then it lives alongside the pipeline and reuses the same analysis logic (not just FastAPI)"
verdict: VALIDATED
related: [001, 002]
tags: [fastapi, rest, architecture, pipelines]
---

# Spike 003: FastAPI /analyze Coexisting with the Pipeline

## What This Validates
The task requires BOTH an OpenWebUI Pipeline (mandatory) AND a REST `POST /analyze` endpoint,
without the REST endpoint "replacing" the Pipeline (explicit disqualifier). This spike settles
how they coexist and share logic.

## Research
- Pipelines server is itself a FastAPI app on 9099, but it auto-loads `class Pipeline` modules;
  bolting custom routes onto its internal app is unsupported/fragile across versions.
- Issue #164 thread confirms pipelines run in a separate container from open-webui.

## Investigation Trail
1. Considered mounting extra routes on the pipelines FastAPI app → rejected: undocumented,
   version-fragile, risks the "must be a real Pipeline" grading.
2. Chosen architecture: **extract the core into a shared Python package**
   (`asr/` + `agents/` + `analysis.py::run_analysis(audio) -> dict`). Then:
   - The **Pipeline** (`pipeline.py`) imports it and calls `run_analysis()` inside `pipe()`,
     formatting the result as chat markdown.
   - A **separate FastAPI service** (`api/main.py`) imports the *same* `run_analysis()` and
     exposes `POST /analyze` (multipart file OR `{"url": ...}`) returning the task's JSON.
3. Both run as their own compose services from one image (spike 002 `api` service). No logic
   duplication — a single source of truth for ASR + agents.

## Results
**VERDICT: VALIDATED.** Shared-core pattern satisfies all three constraints:
- ✅ Real OpenWebUI Pipeline present and doing the orchestration (no disqualifier).
- ✅ REST `POST /analyze` present and robust for direct file upload.
- ✅ Zero duplicated agent/ASR logic — both entrypoints call `run_analysis()`.

Build requirement: keep `run_analysis(audio_source) -> AnalysisResult` framework-agnostic
(pure Python, no OpenWebUI imports) so both the Pipeline and FastAPI can depend on it.
