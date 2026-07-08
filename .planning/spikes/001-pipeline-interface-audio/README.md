---
spike: 001
name: pipeline-interface-audio
type: standard
validates: "Given the external pipelines server, when a user submits audio in OpenWebUI chat, then pipe() actually receives it in a known form — and we know the exact Pipeline/Valves/pipe signature"
verdict: VALIDATED
related: [002, 003]
tags: [openwebui, pipelines, asr, architecture, audio-ingestion]
---

# Spike 001: Pipeline Interface & Audio Ingestion

## What This Validates
Given the external OpenWebUI Pipelines server (port 9099), when a user submits an audio
call in the chat, then `pipe()` reliably receives it in a known form — and we have the exact
verified `Pipeline` / `Valves` / `pipe()` interface to build on.

## Research
Sources (all fetched during spike):
- open-webui/pipelines README — https://github.com/open-webui/pipelines (raw `main/README.md`)
- `examples/pipelines/providers/openai_manifold_pipeline.py`
- Issue #164 "Access uploaded files in pipelines" — https://github.com/open-webui/pipelines/issues/164 (maintainer + community threads)
- OpenWebUI functions special args (`__files__`) — backend/open_webui/functions.py

### Confirmed interface (external Pipelines server)
```python
class Pipeline:
    class Valves(BaseModel): ...          # config, editable live in Admin > Pipelines
    def __init__(self): ...
    async def on_startup(self): ...       # heavy init (load whisper, build agents) — once
    async def on_shutdown(self): ...
    async def on_valves_updated(self): ...            # optional
    async def inlet(self, body: dict, user: dict) -> dict: ...   # optional pre-hook
    def pipe(self, user_message: str, model_id: str,
             messages: List[dict], body: dict) -> Union[str, Generator, Iterator]: ...
    async def outlet(self, body: dict, user: dict) -> dict: ...  # optional post-hook
```
- `pipe()` returns a **str** (rendered as chat markdown) or a **generator** (streaming).
- Server auto-discovers a module-level `class Pipeline` from files in `/app/pipelines`.

## Investigation Trail
1. README only names the pieces (Valves/on_startup/pipe) without full signatures → pulled the manifold example → got the canonical `pipe(user_message, model_id, messages, body)` and `Union[str, Generator, Iterator]` return.
2. Core unknown: **how does uploaded audio reach `pipe()`?** Searched OpenWebUI docs/issues.
3. Found the split: `__files__` is a **Functions (in-process Pipe)** special arg — NOT the external Pipelines mechanism. The task mandates **Pipelines**, so `__files__` does not apply.
4. Issue #164 (maintainer InquestGeronimo + community): in Pipelines, uploaded files surface only inside `inlet(self, body, user)` as `body["files"]` → each has a `url`; content fetched via `file["url"] + "/content"`.
5. **Critical gotchas** from the same thread:
   - OpenWebUI **pre-parses** uploaded documents to text (CSV/HTML get mangled). Binary **audio** does not cleanly round-trip this path.
   - The pipelines container is **separate** from open-webui; it cannot read the uploads dir unless the volume is mounted, and fetching `/content` needs a WebUI API key.
   - Conclusion: chat **file upload of raw audio is fragile** for our use case.

## Results
**VERDICT: VALIDATED** — interface fully confirmed; audio-ingestion risk resolved with a concrete decision.

**Decision (→ becomes a build requirement):**
- **Primary audio path = URL in the chat message.** `pipe()` reads `messages[-1]["content"]`, regex-extracts an audio URL, downloads it directly. This matches the task's own skeleton (`_extract_audio(body)`) and FAQ ("загрузка через чат или URL").
- **Direct file upload is served by REST `POST /analyze`** (multipart) — see spike 003 — which is robust and is also a hard requirement of the task.
- Optional stretch: also support chat file-upload via `inlet` + `url`/`/content`, documented as best-effort.

**Surprise / strong README ammo:** the pipelines README now literally says **"DO NOT USE PIPELINES!"** — steering simple cases to Functions — *except* for "computationally heavy tasks you want to offload from your main Open WebUI instance." Our whisper-ASR + 4-agent workload is exactly that justified case. This is the argument for the mandatory-Pipelines requirement in our README.

See `pipeline_skeleton.py` for the verified reference skeleton.
