---
phase: quick-260710-mue
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - mtbank/agents/trends.py
  - mtbank/batch.py
  - tests/test_trends.py
  - tests/conftest.py
  - api/main.py
  - pipelines/mtbank_pipeline.py
  - tests/test_api.py
  - README.md
autonomous: true
requirements:
  - BONUS-A-TRENDS
must_haves:
  truths:
    - "POST /analyze-batch with 2+ sources returns deterministic aggregates + LLM trend judgement as JSON."
    - "A chat message with more than one audio URL renders a Russian trends markdown report; a single-URL message behaves EXACTLY as before."
    - "Deterministic aggregates (call count, topic distribution, avg/min/max quality, per-checklist pass rate, compliance failure rate, forbidden-phrase frequency) are computed IN CODE and remain present even when the LLM fails."
    - "One failing call in the batch does not sink the batch — it is recorded as an error and the rest are still analyzed."
    - "tests/test_trends.py passes and the full pre-existing suite (44 tests) stays green."
  artifacts:
    - mtbank/agents/trends.py
    - mtbank/batch.py
    - tests/test_trends.py
    - "api/main.py POST /analyze-batch"
    - "pipelines/mtbank_pipeline.py batch branch"
    - "README.md trends section + fixed limitations bullet + measured test count"
  key_links:
    - "run_batch_analysis reuses run_analysis() — no duplicated ASR/agent logic."
    - "trends.run computes deterministic aggregates independent of the LLM; only the judgement fields degrade on LLM failure."
    - "pipeline batch branch keys off >1 UNIQUE audio URL; the single-URL path is untouched."
    - "FakeLLM drives trends via DEFAULT_RESPONSES['trends']; no real LLM is ever called in a test."
---

<objective>
Implement Bonus A from `.planning/HANDOFF.md`: a fifth LLM agent that analyzes MULTIPLE calls
and surfaces patterns, exposed via REST `POST /analyze-batch` and a chat batch mode.

Purpose: +5 points on the rubric, at 0 ₽ marginal cost. It also demonstrates the project's core
principle at batch scale — numbers are computed by CODE (like `quality.compute_total`), and the
LLM is used ONLY for judgement (patterns, causes, recommendations, semantic grouping).

Output: `mtbank/agents/trends.py`, `mtbank/batch.py` (`run_batch_analysis`), a REST endpoint, a
chat batch branch, `tests/test_trends.py`, and README documentation with a MEASURED test count.
</objective>

<execution_context>
@$HOME/.claude-work/gsd-core/workflows/execute-plan.md
@$HOME/.claude-work/gsd-core/templates/summary.md
</execution_context>

<context>
@.claude/CLAUDE.md
@.planning/HANDOFF.md
@README.md

# The exact shape every agent follows (module-level NAME, SYSTEM, run(), fallback()):
@mtbank/agents/quality.py
@mtbank/agents/classifier.py
@mtbank/agents/compliance.py
@mtbank/agents/summarizer.py
@mtbank/agents/supervisor.py
@mtbank/agents/llm.py
@mtbank/analysis.py
@mtbank/errors.py
@api/main.py
@pipelines/mtbank_pipeline.py
@tests/conftest.py
@tests/test_agents.py
@tests/test_pipeline.py
@tests/test_api.py
</context>

<constraints>
- Commits are authored by `ib0gdan` ONLY. NEVER add a `Co-Authored-By: Claude` trailer or any
  Claude attribution. Hard user requirement.
- This runs on the MAIN working tree at `/Users/ivanbogdan/Documents/test-tasks/mtbank-ai-hiring`,
  NOT a git worktree — the docker containers bind-mount the main checkout, so a worktree's edits
  would be invisible to pytest and produce a false green. Edit files in place.
- Tests run as `docker compose exec -T api pytest -q` (container bind-mounts ./mtbank, ./tests,
  ./api). Fast subset: `docker compose exec -T api pytest -q -m "not slow"`.
- After editing `mtbank/`, recreate the pipelines container so it picks up the new module:
  `docker compose up -d --force-recreate pipelines` (it holds the module in memory).
- Do NOT touch the `requirements:` line in `pipelines/mtbank_pipeline.py` frontmatter — it must
  stay the bare package list `requests`; an inline comment there is fed to pip verbatim, the
  install fails, and the pipelines server quarantines the file into `pipelines/failed/`.
- The `POST /analyze` response contract keys are fixed by the задание — do NOT change them.
- All 44 existing tests must stay green (baseline verified: 44 passed).
- Do NOT hardcode invented numbers into README. Every timing/count must be MEASURED first.
- Code comments explain WHY (constraints, rationale), never what the next line does. Module
  docstrings in the existing Russian/English mixed style of the other agents.
- LLM is ALWAYS faked in tests via `tests/conftest.py::FakeLLM`. Never call the real LLM in a test.
</constraints>

<design_decisions>
These are settled decisions the executor implements (they resolve the open questions in the task).

1. **Deterministic layer lives in `compute_aggregates(calls)` — pure code, no LLM.** Mirrors
   `quality.compute_total`. It consumes a list of `run_analysis()` result dicts and returns:
   `num_calls`, `topics` (count per `classification.topic`), `quality` (`avg`/`min`/`max` over
   `quality_score.total`), `checklist_pass_rate` (fraction True per checklist key), 
   `compliance_failure_rate` (fraction with `compliance.passed == False`), and
   `forbidden_phrase_hits` (frequency of each deterministic rule hit). Read every field with
   `.get(..., default)` so a degraded/partial call (one with `agent_errors`) never crashes it.
2. **`forbidden_phrase_hits` reuses `compliance.check_forbidden(call["transcript"])`** rather than
   parsing issue strings — the deterministic rule set stays the single source of truth, and LLM-
   paraphrased issues can never contaminate the count.
3. **LLM layer is judgement ONLY.** `trends.run` calls the LLM once for
   `{"patterns", "causes", "recommendations", "grouped_action_items", "grouped_compliance_issues"}`.
   The prompt says explicitly "не считай числа сам — агрегаты уже посчитаны кодом". Semantic
   grouping is delegated to the LLM because the same task/violation is worded differently every
   call, so exact string equality cannot group them.
4. **LLM failure NEVER loses the deterministic aggregates.** `trends.run` wraps the LLM call in
   try/except: on failure it logs and keeps the empty-judgement defaults, then returns
   `{**aggregates, **judgement}`. This is the whole point of the split — code survives, the model
   is optional.
5. **Batch runs calls SEQUENTIALLY, and this is deliberate.** Each `run_analysis` does its own
   faster-whisper pass, which is CPU-bound and already saturates the 2-vCPU target host (the model
   is a shared warm singleton, but inference activations + waveforms are per concurrent call).
   Running N calls concurrently would oversubscribe the CPU (≈no wall-clock win on the dominant ASR
   stage) while multiplying peak memory — dangerous on a 2 GB VPS. The existing supervisor's
   parallelism is a different situation: 4 network-bound LLM round-trips WITHIN one call. So keep
   intra-call parallelism, run inter-call sequentially. Document this rationale as a WHY comment.
6. **One failing call must not sink the batch.** `run_batch_analysis` wraps each per-source
   `run_analysis` in try/except. Successful analyses go into `calls`; failures go into `errors`
   as `{"source", "code", "message"}`. Trends is computed over `calls` (successes) only. If every
   call fails (or `sources` is empty) → `calls == []` → safe empty aggregates, no division by zero.
7. **Batch size is capped** (`MAX_BATCH_SOURCES`, e.g. 20) to bound the amplified fetch/CPU cost
   (a batch endpoint multiplies the existing single-call resource + SSRF surface). Over the cap →
   `AnalysisError(code="batch_too_large")` → HTTP 400.
8. **Return shape:** `run_batch_analysis(sources) -> {"calls": [...], "errors": [...],`
   `"trends": {...}, "request_id": ..., "elapsed_s": ...}`. `elapsed_s` is a real `time.time()`
   delta (a measurement, not an invented doc number).
</design_decisions>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Trends agent + deterministic aggregates + batch core (test-first)</name>
  <files>mtbank/agents/trends.py, mtbank/batch.py, tests/conftest.py, tests/test_trends.py</files>
  <behavior>
    Write these tests in tests/test_trends.py FIRST (following tests/test_agents.py style), watch
    them fail, then implement. LLM is always FakeLLM. First extend
    tests/conftest.py::DEFAULT_RESPONSES with a "trends" entry, e.g.
    {"patterns": ["Клиенты часто жалуются на списания"], "causes": ["..."],
     "recommendations": ["Обучить операторов disclaimer"], "grouped_action_items": ["Отправить условия кредита"],
     "grouped_compliance_issues": ["Отсутствует disclaimer о решении банка"]}.

    Build a small helper in the test that fabricates run_analysis-shaped dicts (transcript +
    classification + quality_score.checklist/total + compliance.passed/issues + action_items).

    - compute_aggregates over a hand-built list of 3 calls: assert num_calls==3, topics counts
      match, quality avg/min/max correct, checklist_pass_rate fractions correct, and
      compliance_failure_rate correct.
    - forbidden_phrase_hits: include one call whose operator transcript contains a known forbidden
      phrase (reuse the bad_transcript wording, e.g. "гарантирую одобрение") — assert that phrase
      is tallied via compliance.check_forbidden, and a clean batch tallies zero.
    - Empty list: compute_aggregates([]) → num_calls==0, no crash, quality values None (or 0),
      rates 0.0; trends.run over an empty list returns safe empties WITHOUT calling the LLM.
    - Single call: aggregates sane (avg==min==max==that call's total; topics has one entry).
    - LLM judgement merged: trends.run(calls, FakeLLM()) → patterns/recommendations from
      DEFAULT_RESPONSES["trends"] present, AND deterministic aggregates present in the same dict.
    - Degradation on LLM failure: trends.run(calls, FakeLLM(fail=("trends",))) → aggregates STILL
      present and correct; judgement fields fall back to empty lists. (The critical test.)
    - Coercion of a garbage model response: FakeLLM({"trends": {"patterns": "не список",
      "recommendations": [1, 2, None, "  ", "ok"]}}) → patterns coerced to [] (non-list),
      recommendations coerced to ["ok"] (ints/None/blank dropped, only non-empty str kept).
    - run_batch_analysis resilience: monkeypatch mtbank.batch.run_analysis so one source raises
      AnalysisError and the others return a fabricated contract → assert `calls` holds the
      successes, `errors` holds the one failure with its code, and `trends.num_calls` == number of
      successes. Also assert an all-fail batch returns calls==[] and safe empty trends.
    - trends.fallback() returns a well-shaped dict (parametrize alongside the other agents' shape
      check if convenient) and trends.NAME == "trends".
  </behavior>
  <action>
Create `mtbank/agents/trends.py` following the EXACT shape of the sibling agents: module docstring
(WHY-style, explain that this is the fifth agent, that it runs AFTER per-call analysis over N
result dicts rather than inside the supervisor fan-out, and that numbers are code / the LLM only
judges), module-level `NAME = "trends"`, a `SYSTEM` prompt, `run(...)`, and `fallback()`.

Deterministic layer — `compute_aggregates(calls: list[dict]) -> dict`:
- `num_calls`, `topics` (Counter over `call.get("classification", {}).get("topic", "другое")`),
  `quality` with `avg`/`min`/`max` over `call.get("quality_score", {}).get("total", 0)` (None-safe
  when empty — no crash, no division by zero), `checklist_pass_rate` (per checklist key, fraction
  of calls where it is truthy — iterate the keys present on the calls, do not hardcode them),
  `compliance_failure_rate` (fraction with `compliance.passed` falsey), and `forbidden_phrase_hits`
  built by tallying `compliance.check_forbidden(call.get("transcript", []))` across calls (import
  `check_forbidden` from `.compliance` — reuse, do not re-implement the rule set).
- Read every field defensively with `.get`, so a degraded call (one carrying `agent_errors`) or a
  malformed dict is aggregated without raising.

LLM layer — `run(calls, llm, request_id="-")`:
- Compute `aggregates = compute_aggregates(calls)` first. If `not calls`, return
  `{**aggregates, **_empty_judgement()}` WITHOUT calling the LLM.
- Otherwise build a compact Russian digest string of the batch (per call: topic, quality total,
  compliance verdict, its action_items and issues) plus the aggregates, and call
  `llm.complete_json(SYSTEM, digest, agent=NAME, request_id=request_id)`. The `SYSTEM` prompt asks
  for JSON `{"patterns", "causes", "recommendations", "grouped_action_items",`
  `"grouped_compliance_issues"}`, tells the model NOT to compute numbers (already done in code),
  and to group semantically similar action items / issues.
- Wrap the LLM call in try/except (log via the module logger + `log_event`, like the supervisor
  logs `agent_failed`): on ANY exception keep `_empty_judgement()` — the deterministic aggregates
  must survive. Coerce each judgement field with a strict helper: keep only non-empty `str`
  instances after `.strip()`, drop ints/None/blanks, treat a non-list value as `[]`, cap the list
  length. Return `{**aggregates, **judgement}`.
- `fallback()` returns the full safe dict shape: `{**_empty_aggregates(), **_empty_judgement()}`
  (matches the other agents' "fallback returns the same shape" contract).

Create `mtbank/batch.py` with `run_batch_analysis(sources, *, llm=None, request_id=None) -> dict`
(module docstring in the existing style, WHY the batch is sequential — decision 5):
- `sources` items are either a `str` (url/path) or a `(audio_bytes|str, filename)` tuple; normalize
  each into `(audio_source, filename)`.
- Enforce `MAX_BATCH_SOURCES` (e.g. 20): over the cap raise `AnalysisError(..., code="batch_too_large")`.
- Iterate SEQUENTIALLY. For each source, derive a per-call `request_id` (e.g. f"{rid}-{i}") and call
  `run_analysis(audio, filename=filename, request_id=..., llm=llm)` inside try/except `AnalysisError`
  (and a broad `Exception` guard so one bad call never sinks the batch). Successes append to `calls`;
  failures append `{"source", "code", "message"}` to `errors`.
- Compute `trends = trends_agent.run(calls, llm or LLMClient(), request_id=rid)`, guarded by
  try/except → `trends_agent.fallback()` as a final safety net.
- Return `{"calls": calls, "errors": errors, "trends": trends, "request_id": rid,`
  `"elapsed_s": round(time.time() - started, 2)}`. Reuse `run_analysis` — do NOT duplicate any
  ASR/agent logic.

Extend `tests/conftest.py::DEFAULT_RESPONSES` with a `"trends"` entry (canned judgement dict) so
FakeLLM can drive the agent. Do NOT alter the existing entries.
  </action>
  <verify>
    <automated>docker compose exec -T api pytest -q tests/test_trends.py && docker compose exec -T api pytest -q -m "not slow"</automated>
  </verify>
  <done>tests/test_trends.py passes; the fast subset (existing 44 minus slow + new trends tests) is green; deterministic aggregates are present even under FakeLLM(fail=("trends",)); a one-call-fails batch keeps its successes and records the failure.</done>
</task>

<task type="auto">
  <name>Task 2: Wire both interfaces — REST /analyze-batch + chat batch mode</name>
  <files>api/main.py, pipelines/mtbank_pipeline.py, tests/test_api.py</files>
  <action>
REST — add `POST /analyze-batch` to `api/main.py` (import `run_batch_analysis` from `mtbank.batch`):
- Accept a list of urls AND/OR several uploaded files. JSON body `{"urls": [...]}`; multipart with
  repeated `files` fields plus optional `urls`. Build the `sources` list: url strings as-is; each
  uploaded file as `(await upload.read(), upload.filename)` so the extension survives.
- If no sources → HTTP 400 like `/analyze`. Call `run_batch_analysis(sources, request_id=rid)` and
  return its dict. Map `AnalysisError` → HTTP 400 `{"code", "message"}` exactly as `/analyze` does
  (this also surfaces `batch_too_large`). Do NOT change the existing `/analyze` handler or its keys.

Chat — add batch mode to `pipelines/mtbank_pipeline.py` (import `run_batch_analysis`; do NOT touch
the `requirements:` frontmatter line):
- Replace the single `_AUDIO_URL_RE.search` branch logic in `pipe()` with: collect ALL matches via
  `_AUDIO_URL_RE.findall(user_message or "")`, dedupe preserving order. If the deduped count is
  > 1 → batch mode: call `run_batch_analysis([...urls...])` and render with a NEW
  `_format_trends_markdown(batch_result)`. If the count is exactly 1 → the EXISTING single-URL path
  UNCHANGED (`run_analysis(url)` → `_format_markdown`). If 0 → the existing assistant/empty paths,
  unchanged.
- `_format_trends_markdown` renders Russian markdown in the style of `_format_markdown` (`###`
  sections, bold, bullets): a header with the call count; topic distribution; average/min/max
  quality; checklist pass rates; compliance failure rate + forbidden-phrase frequency; then the
  LLM judgement (паттерны / вероятные причины / рекомендации / сгруппированные задачи и нарушения);
  a compact per-call line list (тема · качество · комплаенс); and a `> ⚠️` warning line listing any
  `errors` (mirror the existing `agent_errors` rendering). Reuse the `_PRIORITY_RU`/`_CHECKLIST_RU`
  label maps where relevant.

Extend `tests/test_api.py` with a `/analyze-batch` happy-path test: monkeypatch
`api.main.run_batch_analysis` to return a canned `{"calls": [...], "errors": [], "trends": {...}}`
and assert the endpoint returns it with 200 (mirror `test_analyze_json_url_returns_contract`). Do
not exercise the real LLM/ASR here.

After editing `mtbank/` (Task 1) and the pipeline, recreate the affected containers so the live
demo serves the new code: `docker compose up -d --force-recreate api pipelines`.
  </action>
  <verify>
    <automated>docker compose up -d --force-recreate api pipelines && docker compose exec -T api pytest -q tests/test_api.py</automated>
  </verify>
  <done>tests/test_api.py passes including the new /analyze-batch test; the existing /analyze tests and contract are unchanged; the single-URL chat path is byte-for-byte the same behaviour.</done>
</task>

<task type="auto">
  <name>Task 2.5: Live end-to-end verification of BOTH interfaces (real ASR + real Groq)</name>
  <files></files>
  <action>
Drive the real stack — no mocks, no browser. This is the task's proof, so DO NOT skip it and do NOT
declare success from unit tests alone. Both containers must already be recreated (Task 2).

1. REST batch, two real recordings served by the `files` container:
   ```
   curl -sS -X POST http://localhost:8000/analyze-batch \
        -H "Content-Type: application/json" \
        -d '{"urls":["http://files/call_card_blocked.mp3","http://files/call_credit_consultation.wav"]}'
   ```
   Assert the JSON has `calls` (length 2), `errors` ([]), and `trends` carrying real deterministic
   aggregates (`num_calls == 2`, a `topics` distribution, `quality.avg/min/max`). Record the real
   `elapsed_s` — it is a MEASUREMENT you may later cite.

2. Batch resilience against a genuinely broken source (one good url + one 404):
   ```
   curl -sS -X POST http://localhost:8000/analyze-batch -H "Content-Type: application/json" \
        -d '{"urls":["http://files/call_dialog.mp3","http://files/does-not-exist.mp3"]}'
   ```
   Assert `calls` has 1 entry, `errors` has 1 entry with a `code`, and `trends.num_calls == 1`.
   This proves decision 6 on the live stack, not just under monkeypatch.

3. CHAT path through the real OpenWebUI Pipelines server (OpenAI-compatible, port 9099 — this is
   the interface the задание grades, so it must be exercised for real). Discover the model id then
   send TWO urls in one message:
   ```
   curl -sS http://localhost:9099/models -H "Authorization: Bearer ${PIPELINES_API_KEY:-0p3n-w3bu!}"
   curl -sS -X POST http://localhost:9099/chat/completions \
        -H "Authorization: Bearer ${PIPELINES_API_KEY:-0p3n-w3bu!}" \
        -H "Content-Type: application/json" \
        -d '{"model":"<id from /models>","stream":false,"messages":[{"role":"user","content":"Проанализируй звонки: http://files/call_card_blocked.mp3 http://files/call_credit_consultation.wav"}]}'
   ```
   Assert the returned markdown is the Russian TRENDS report (group header, topic distribution,
   quality aggregates, LLM patterns/recommendations) — not a single-call report.

4. REGRESSION — the single-URL chat path must be untouched. Same endpoint, ONE url:
   `"content":"Проанализируй звонок: http://files/call_dialog.mp3"`
   Assert the markdown is the ORIGINAL single-call layout (`## 📞 Анализ звонка`, Транскрипт,
   Классификация, Качество обслуживания, Комплаенс, Резюме, Задачи после звонка).

If any assertion fails, FIX the code and re-run until all four pass. Report the measured `elapsed_s`
of the 2-call batch in the SUMMARY (a real number, not an estimate).
  </action>
  <verify>
    <automated>curl -sS -X POST http://localhost:8000/analyze-batch -H "Content-Type: application/json" -d '{"urls":["http://files/call_card_blocked.mp3","http://files/call_credit_consultation.wav"]}' | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['calls'])==2, d; assert d['errors']==[], d; assert d['trends']['num_calls']==2, d; print('OK batch elapsed_s=', d['elapsed_s'])"</automated>
  </verify>
  <done>Live REST batch returns 2 calls + real trends; a 404 source degrades to `errors` without sinking the batch; the real pipelines chat endpoint renders the trends report for 2 URLs AND the unchanged single-call report for 1 URL.</done>
</task>

<task type="auto">
  <name>Task 3: README — trends section, fixed limitation bullet, MEASURED test count</name>
  <files>README.md</files>
  <action>
Update `README.md` to document the trends agent. Do NOT invent any number — MEASURE first.

1. Measure the real suite AFTER Tasks 1-2 are green:
   `docker compose exec -T api pytest -q` → read the final "N passed" line. Get per-file counts with
   `docker compose exec -T api pytest tests/test_trends.py --co -q | grep -c "::"` (and the same for
   test_api.py, whose count grew by the new batch test). These measured numbers are the ONLY numbers
   allowed into the README.
2. Architecture: extend the mermaid diagram to show the batch path — a `run_batch_analysis` entry
   that fans `run_analysis` over N calls (sequentially), feeding a 📊 **Trends** agent that emits the
   trends JSON; annotate that the Trends agent's numbers are computed in code and the LLM only judges.
3. Add a section (near "Обоснование решений" or a new "Агент трендов" heading) explaining: the
   deterministic layer (what `compute_aggregates` computes in code — the same principle as
   `quality_score.total`), the LLM-judgement layer (patterns/causes/recommendations + semantic
   grouping, and WHY grouping needs an LLM), the sequential-batch decision (decision 5 rationale),
   the one-call-fails-does-not-sink-the-batch behaviour, and the `POST /analyze-batch` endpoint with
   a curl example returning `{calls, errors, trends}`.
4. Fix the "Известные ограничения" bullet that currently reads
   "**Бонусные задания** (real-time WebSocket, Grafana, агент трендов) не реализованы." — remove
   "агент трендов" from the not-implemented list (it is now implemented); leave WebSocket/Grafana.
5. Update the "Тесты" section: the header/bash comments that say "44 теста" → the MEASURED count;
   bump the `tests/test_api.py` row; add a `tests/test_trends.py | N | ...` row with its measured
   count; update the table total to the measured sum.
  </action>
  <verify>
    <automated>docker compose exec -T api pytest -q | tail -1 && test "$(grep -c 'Grafana, агент трендов) не реализованы' README.md)" = "0" && test "$(grep -c '44 теста' README.md)" = "0"</automated>
  </verify>
  <done>Full suite green; README documents the trends agent and /analyze-batch with the deterministic/LLM split; the stale "агент трендов ... не реализованы" claim is gone; every test-count figure in README equals the measured pytest output (no "44 теста" remains).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → `POST /analyze-batch` | Untrusted list of urls/files crosses into the fetch+ASR+LLM pipeline. A batch multiplies the existing single-call resource and SSRF surface. |
| chat message → pipeline batch branch | Untrusted message text parsed for multiple audio URLs. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-mue-01 | Denial of Service | `/analyze-batch` + `run_batch_analysis` | high | mitigate | Cap sources at `MAX_BATCH_SOURCES` → `AnalysisError(code="batch_too_large")` → HTTP 400. Sequential execution bounds peak CPU/RAM (decision 5). |
| T-mue-02 | Denial of Service | one poisoned/slow url in a batch | medium | mitigate | Per-call try/except: a failing call is recorded in `errors` and never sinks the batch; existing per-request `_TIMEOUT` bounds each fetch/LLM. |
| T-mue-03 | Information Disclosure | error surface of `/analyze-batch` | low | mitigate | Reuse `AnalysisError.message` (safe Russian text) + `code`; never leak stack traces — same mapping as `/analyze`. |
| T-mue-SSRF | Information Disclosure | url fetching (inherited from `/analyze`) | medium | accept | SSRF exposure is pre-existing in `run_analysis`'s fetch layer and unchanged by this batch wrapper; out of scope for this bonus, tracked as an existing property. |

No new packages are installed (reuses `requests`, already vendored). No package legitimacy gate required.
</threat_model>

<verification>
- `docker compose exec -T api pytest -q` → all pre-existing 44 tests plus the new trends and batch
  tests are green (final "N passed" line, N > 44).
- Deterministic aggregates survive `FakeLLM(fail=("trends",))` — proven by a dedicated test.
- A one-call-fails batch keeps its successes and records the failure — proven by a dedicated test.
- `/analyze` contract keys unchanged (existing test_api tests still pass).
- Single-URL chat path unchanged (existing pipeline behaviour preserved; only the >1-URL branch is new).
- README contains no invented numbers: every test-count figure equals the measured pytest output.
</verification>

<success_criteria>
- `mtbank/agents/trends.py` exists with `NAME`, `SYSTEM`, `run`, `fallback`; numbers computed in
  code, LLM used only for judgement.
- `mtbank/batch.py::run_batch_analysis` reuses `run_analysis`, runs sequentially, survives a failing
  call, returns `{calls, errors, trends, request_id, elapsed_s}`.
- `POST /analyze-batch` accepts urls and/or uploaded files; chat renders a Russian trends report for
  >1 audio URL and is unchanged for a single URL.
- `tests/test_trends.py` covers aggregates, empty/single-call, LLM-failure degradation, garbage
  coercion, and batch resilience — all with FakeLLM.
- README documents the agent + endpoint and no longer claims the trends agent is unimplemented; test
  count is measured.
- All commits authored by `ib0gdan`, no Claude attribution.
</success_criteria>

<output>
Create `.planning/quick/260710-mue-trends-agent/260710-mue-SUMMARY.md` when done.
</output>
