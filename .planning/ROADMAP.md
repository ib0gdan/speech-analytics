# Roadmap: MTBank Call Analytics — AI Engineer Test Task

## Overview

Five phases carry the project from an empty repo to a submitted test task. Phase 1 deploys a
thin, fully-wired, end-to-end skeleton (docker-compose stack, OpenWebUI chat, REST `/analyze`,
shared `run_analysis()` core, JSON logging) to a live HTTPS host on day one — using a stub
transcript and one trivial agent — so the deploy path is de-risked before real ASR or agent
logic exists. Phase 2 swaps the stub transcript for real faster-whisper transcription plus
Operator/Client diarization (the one genuinely open risk from the spike). Phase 3 swaps the
trivial stub agent for the real 4-agent analysis (classifier, quality, compliance, summarizer)
orchestrated through the Pipeline. Phase 4 locks in correctness with automated tests. Phase 5
adds the evaluation test set, WER table, Russian README, and re-verifies the live demo against
the <60s/5-min performance bar for final submission. Bonuses (real-time WebSocket, Grafana,
trend agent) are explicitly out of v1 scope.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Deployed Skeleton (End-to-End Vertical Slice)** - Stubbed audio→JSON path live on HTTPS, proving docker-compose + Pipeline + REST + shared core work together
- [ ] **Phase 2: Real ASR & Diarization** - faster-whisper transcription + Operator/Client speaker split replaces the stub transcript
- [ ] **Phase 3: Multi-Agent Analytics & Orchestration** - The 4 real analysis agents replace the trivial stub agent, orchestrated via the Pipeline
- [ ] **Phase 4: Automated Testing & Robustness** - pytest suite verifies every agent and the full pipeline end-to-end
- [ ] **Phase 5: Test Data, Evaluation, Docs & Final Demo** - WER-scored test set, Russian README, and a finalized live demo under the 60s bar

## Phase Details

### Phase 1: Deployed Skeleton (End-to-End Vertical Slice)
**Goal**: A user can reach a working audio→JSON analysis path through either OpenWebUI chat or REST `/analyze`, live on a public HTTPS demo, even though ASR and agent logic are stubbed — so the deployment path is proven before real complexity is added.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, CORE-01, API-01, UI-01
**Success Criteria** (what must be TRUE):
  1. `docker compose up` brings up openwebui + pipelines + api together with no extra manual steps
  2. The stubbed stack is deployed and publicly reachable over HTTPS — de-risking the final live demo before real ASR/agents exist
  3. Pasting an audio URL in OpenWebUI chat, or `POST`-ing to `/analyze` (multipart file or `{url}`), returns a JSON analysis (stub transcript + 1 trivial agent) built from one shared `run_analysis()` core used by both entry points
  4. `.env`/`.env.example` hold `GROQ_API_KEY` and `PIPELINES_API_KEY` — no secret is hardcoded anywhere in the code
  5. Every stub agent call in the flow is captured as a structured JSON log line with input/output, ready to extend to real agents
**Plans**: TBD

### Phase 2: Real ASR & Diarization
**Goal**: The skeleton's stub transcript is replaced with a real faster-whisper transcription and an Operator/Client speaker split, working through both entry points on real Russian audio — the one genuinely open risk flagged by the spike, sequenced early.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: ASR-01, ASR-02, ASR-03, ASR-04, ASR-05
**Success Criteria** (what must be TRUE):
  1. Given a real Russian audio URL or file, the pipeline returns a transcript produced by faster-whisper (small int8, built-in VAD) rather than the phase-1 stub
  2. At least two of WAV/MP3/OGG are accepted and transcribed correctly
  3. The transcript comes back as segments, each carrying speaker/start/end/text fields
  4. Each segment's speaker is labeled Operator or Client via the no-pyannote VAD+heuristic diarizer
  5. A corrupt file, an unreachable URL, or empty/silent audio produces a clear, specific error message instead of a crash or silent failure
**Plans**: TBD

### Phase 3: Multi-Agent Analytics & Orchestration
**Goal**: The phase-1 trivial stub agent is replaced by the real 4-agent analysis running over the real transcript, orchestrated through the OpenWebUI Pipeline, producing the full analysis payload end-to-end.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, ORCH-01
**Success Criteria** (what must be TRUE):
  1. The classifier returns a topic (кредиты/карты/переводы/жалобы) and a priority for a given transcript
  2. The quality agent returns a checklist (приветствие, выявление потребности, решение, прощание) plus a total score
  3. The compliance agent returns `passed` + `issues`, flagging forbidden phrases or missing required disclaimers
  4. The summarizer returns a 3-5 sentence summary plus a list of `action_items`
  5. All 4 agents run through one documented orchestration (LangGraph or Supervisor) invoked from the Pipeline, with the choice justified
**Plans**: TBD

### Phase 4: Automated Testing & Robustness
**Goal**: The full pipeline (real ASR + 4 real agents + orchestration) is verified correct by an automated test suite runnable with one command, catching regressions before the final demo push.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: TEST-01, TEST-02
**Success Criteria** (what must be TRUE):
  1. Running pytest executes a unit test for each of the 4 agents against a fixed transcript fixture, and all pass
  2. Running pytest executes an integration test that drives the full pipeline from an audio input to a final JSON result, and it passes
**Plans**: TBD

### Phase 5: Test Data, Evaluation, Docs & Final Demo
**Goal**: The project ships with a reproducible Russian test-audio set with reference transcripts, a WER evaluation proving ASR accuracy, a complete Russian README tying the architecture and decisions together, and a finalized live HTTPS demo re-verified against the <60s/5-min performance bar for submission.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: DATA-01, DATA-02, DOCS-01, DEMO-01
**Success Criteria** (what must be TRUE):
  1. `test_data/` contains 5+ Russian audio files (including an 8kHz telephone recording and a 1min+ two-speaker dialog, 5+ minutes total) each with a reference transcript
  2. Running the WER evaluation (jiwer) against all test files produces a table attached to the README
  3. README.md (Russian) documents the architecture diagram, run instructions, and the rationale behind the Pipeline/LLM/ASR-model/orchestration choices
  4. The live HTTPS demo on the ≥2 vCPU CPU host responds in under 60 seconds for a file up to 5 minutes, confirmed end-to-end after all real ASR/agent logic is in place
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Deployed Skeleton (End-to-End Vertical Slice) | 0/TBD | Not started | - |
| 2. Real ASR & Diarization | 0/TBD | Not started | - |
| 3. Multi-Agent Analytics & Orchestration | 0/TBD | Not started | - |
| 4. Automated Testing & Robustness | 0/TBD | Not started | - |
| 5. Test Data, Evaluation, Docs & Final Demo | 0/TBD | Not started | - |
