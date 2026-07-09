"""WER evaluation over the RU test corpus (DATA-02).

Transcribes every file in test_data/ with the project's own ASR stack and scores it against the
reference transcript with `jiwer`.

Normalisation matters more than the number itself. Whisper writes "15 тысяч" and "18%" where the
reference (the TTS input) says "пятнадцать тысяч" and "восемнадцати процентов". Scoring those as
errors would measure our formatting, not our recognition. So both sides are normalised: lowercase,
ё→е, punctuation stripped, "%" expanded, and digit tokens spelled out in Russian.

The model is warmed up before timing, otherwise the first file absorbs the model load and the
realtime factor is meaningless.

Usage:
    docker compose exec api python scripts/eval_wer.py                 # default: small
    docker compose exec api python scripts/eval_wer.py --model medium  # for the model comparison
    docker compose exec api python scripts/eval_wer.py --worst         # show the worst file's diff
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import jiwer
from num2words import num2words

sys.path.insert(0, "/app")

TEST_DATA = Path("/app/test_data")
AUDIO_EXT = (".wav", ".mp3", ".ogg")

_PUNCT = re.compile(r"[^\w\s%]", re.UNICODE)
_DIGITS = re.compile(r"\d+")
_SPACES = re.compile(r"\s+")


def _spell_digits(match: re.Match) -> str:
    return num2words(int(match.group()), lang="ru")


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = text.replace("%", " процентов ")
    text = _PUNCT.sub(" ", text)
    text = _DIGITS.sub(_spell_digits, text)
    return _SPACES.sub(" ", text).strip()


def audio_duration(path: Path) -> float:
    """Duration via our own decoder — the api image has no ffprobe binary."""
    from mtbank.asr.audio import SAMPLE_RATE, decode_waveform

    return len(decode_waveform(path)) / SAMPLE_RATE


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("WHISPER_MODEL", "small"))
    parser.add_argument("--worst", action="store_true", help="print the worst file's word diff")
    args = parser.parse_args()

    os.environ["WHISPER_MODEL"] = args.model
    from mtbank.asr.transcriber import transcribe  # imported after the env is set

    files = sorted(p for p in TEST_DATA.iterdir() if p.suffix.lower() in AUDIO_EXT)
    files = [f for f in files if f.with_suffix(".txt").exists()]
    if not files:
        print("no audio+reference pairs in test_data/", file=sys.stderr)
        return 1

    transcribe(files[0])                                  # warm-up: load the model off the clock

    rows, refs, hyps = [], [], []
    for audio in files:
        started = time.time()
        segments = transcribe(audio)
        elapsed = time.time() - started

        hyp = normalize(" ".join(s["text"] for s in segments))
        ref = normalize(audio.with_suffix(".txt").read_text(encoding="utf-8"))
        refs.append(ref)
        hyps.append(hyp)

        duration = audio_duration(audio)
        rows.append({
            "file": audio.name, "ref": ref, "hyp": hyp,
            "wer": jiwer.wer(ref, hyp), "cer": jiwer.cer(ref, hyp),
            "words": len(ref.split()), "elapsed": elapsed, "duration": duration,
            "rtf": duration / elapsed,
        })

    total_audio = sum(r["duration"] for r in rows)
    total_time = sum(r["elapsed"] for r in rows)

    print(f"\n### Модель `{args.model}` (int8, CPU)\n")
    print("| Файл | Формат | Слов | WER | CER | Аудио | ASR | Быстрее реального времени |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| `{r['file']}` | {r['file'].split('.')[-1]} | {r['words']} | "
              f"**{r['wer']:.1%}** | {r['cer']:.1%} | {r['duration']:.0f} с | "
              f"{r['elapsed']:.1f} с | {r['rtf']:.1f}× |")
    print(f"| **Итого** | | {sum(r['words'] for r in rows)} | "
          f"**{jiwer.wer(refs, hyps):.1%}** | {jiwer.cer(refs, hyps):.1%} | "
          f"{total_audio:.0f} с | {total_time:.1f} с | **{total_audio / total_time:.1f}×** |")

    est_5min = 300 / (total_audio / total_time)
    print(f"\nОценка для 5-минутного звонка: **~{est_5min:.0f} с** "
          f"({'укладывается' if est_5min < 60 else 'НЕ укладывается'} в лимит 60 с)")

    if args.worst:
        worst = max(rows, key=lambda r: r["wer"])
        print(f"\n#### Разбор худшего файла: `{worst['file']}` (WER {worst['wer']:.1%})\n")
        out = jiwer.process_words(worst["ref"], worst["hyp"])
        print(jiwer.visualize_alignment(out, show_measures=False)[:2500])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
