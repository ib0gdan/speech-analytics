---
spike: 004
name: whisper-cpu-diarization
type: standard
validates: "Given a 5-min RU call on CPU, when running faster-whisper small/medium int8 + light diarization, then we stay under 60s and split Оператор/Клиент without pyannote"
verdict: PARTIAL
related: [002]
tags: [asr, faster-whisper, cpu, diarization, performance]
---

# Spike 004: faster-whisper on CPU + Light Diarization

## What This Validates
Whether the ASR half is feasible on a CPU-only free/cheap host under the task's hard demo
constraint (**response < 60s for a file up to 5 min**), and whether Оператор/Клиент
diarization is achievable without the heavy GPU-oriented pyannote stack.

## Research
Sources:
- SYSTRAN/faster-whisper (README, int8 CPU notes) — https://github.com/SYSTRAN/faster-whisper
- Local Whisper STT benchmarks 2026 — promptquorum / localaimaster (RTF figures)

### Timing (int8, CPU, "modern" multi-core desktop)
| Model | ~Realtime factor | 5-min file (est.) | Under 60s? |
|-------|------------------|-------------------|------------|
| base  | ~8–10×           | ~30–40s           | ✅ yes |
| small | ~6×              | ~50s              | ⚠️ borderline |
| medium| ~5× (or slower)  | ~60s+             | ❌ risky |

**Caveat that matters:** those factors assume a healthy multi-core CPU. On free micro
instances (e.g. Render free ≈ 0.5 vCPU) everything is multiples slower → even `small`
blows past 60s. Host must have **≥2–4 vCPU** (HF Spaces CPU basic = 2 vCPU/16GB free fits).

## Investigation Trail
1. Pulled RTF numbers for int8 CPU across sizes → the 60s line falls right between `small`
   (ok-ish) and `medium` (over).
2. Task text says "medium or higher" but ALSO enforces `<60s` demo + gives ASR-quality 20 pts
   partly for the **WER table** and **error handling**, not raw model size. Reconciled:
   default to **small/base int8** for the live path, expose `WHISPER_MODEL` as a **valve** so
   medium can be shown/benchmarked, and **document the tradeoff + WER table** in README. This
   is a defensible engineering call, not a shortcut.
3. Diarization without pyannote: faster-whisper yields word/segment timestamps. Plan a
   lightweight approach — VAD-based segmentation (faster-whisper has built-in Silero VAD) +
   pause/turn heuristic to split turns, then label Оператор/Клиент via a cheap LLM pass
   (first greeting = Оператор) or alternating-turn heuristic. 2-speaker phone dialog is the
   easy case for this. pyannote kept as an untested stretch (needs HF token + heavy deps).

## Results
**VERDICT: PARTIAL (feasible with constraints).**
- ✅ ASR under 60s is achievable with `small`/`base` int8 on a ≥2-vCPU host.
- ⚠️ `medium` likely violates `<60s` on CPU — use as opt-in valve, not the demo default.
- ⚠️ Diarization approach is reasoned but **not yet empirically tested** — must be validated
  during the build on a real 2-speaker RU phone dialog (this is the one genuinely open risk).

Build requirements emerging:
- Default `WHISPER_MODEL=small`, `compute_type=int8`, built-in VAD on.
- Pick a ≥2-vCPU deploy host; measure real transcription time there early.
- Prototype the 2-speaker heuristic diarizer against a real dialog before committing.
