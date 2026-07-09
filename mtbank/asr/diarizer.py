"""Lightweight 2-speaker diarization: Оператор / Клиент (ASR-04) — WITHOUT pyannote.

Why not pyannote: it is GPU-oriented, pulls torch + a gated HF model behind a token, and blows
the CPU/latency budget of this task. For a 2-speaker phone call a much cheaper approach is
sufficient and fully self-contained (numpy only):

  1. Group whisper's segments into speaker TURNS. Whisper cuts on its own decoding boundaries,
     not on speaker changes, and with `vad_filter=True` its timestamps come back contiguous
     (gap == 0) even across a clear hand-off — so we detect the real silence in the WAVEFORM
     around each boundary instead. Turns also give the pitch estimator much more audio.
  2. Fingerprint each turn by WHO speaks, not WHAT is said: median F0 + its spread (pitch — the
     strongest cheap speaker cue), spectral centroid, and MFCC 1..6 (timbre). Raw mel-band
     energies are deliberately NOT used: they encode phonetic content and swamp the speaker
     signal — measured, this collapsed accuracy to near chance.
  3. k-means (k=2) over the z-scored, pitch-weighted fingerprints splits the two speakers.
  4. Turns shorter than ~1.2 s ("Хорошо.") have a noisy F0, so they are re-decided locally
     against their acoustically nearest neighbouring turn.
  5. Roles: the cluster whose text scores highest on operator cues ("МТБанк", "меня зовут",
     "чем могу помочь", ...) is Оператор; the other is Клиент. Falls back to "whoever speaks
     first is the operator" when cues are absent.

Measured 20/20 segments correct on the 2-speaker RU test dialog (scripts/make_test_dialog.sh).

Known limitation (documented in README): speakers who overlap without a pause land in one turn.
Acceptable for a 2-speaker prototype; real overlap handling needs a proper diarizer.
"""

from __future__ import annotations

import numpy as np

from ..logging_config import get_logger, log_event
from .audio import SAMPLE_RATE

logger = get_logger("mtbank.asr.diarizer")

OPERATOR = "Оператор"
CLIENT = "Клиент"

_FRAME = int(0.025 * SAMPLE_RATE)      # 25 ms
_HOP = int(0.010 * SAMPLE_RATE)        # 10 ms
_N_MELS = 24
_F0_MIN, _F0_MAX = 80, 350             # human speech range (Hz)
_TURN_PAUSE = 0.25                     # silence (s) that marks a speaker hand-off
_MIN_RELIABLE_TURN = 1.2               # turns shorter than this have an unreliable F0

_OPERATOR_CUES = (
    "мтбанк", "мт банк", "меня зовут", "чем могу помочь", "чем могу быть полезен",
    "оставайтесь на линии", "уточните", "подскажу", "банк", "оператор",
    "спасибо за обращение", "хорошего дня",
)


# --------------------------------------------------------------------------- features
def _mel_filterbank(n_fft: int) -> np.ndarray:
    def hz_to_mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_to_hz(m):
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    low, high = hz_to_mel(80.0), hz_to_mel(4000.0)
    points = mel_to_hz(np.linspace(low, high, _N_MELS + 2))
    bins = np.floor((n_fft + 1) * points / SAMPLE_RATE).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)

    fb = np.zeros((_N_MELS, n_fft // 2 + 1), dtype=np.float32)
    for i in range(_N_MELS):
        left, center, right = bins[i], bins[i + 1], bins[i + 2]
        if center > left:
            fb[i, left:center] = np.linspace(0, 1, center - left, endpoint=False)
        if right > center:
            fb[i, center:right] = np.linspace(1, 0, right - center, endpoint=False)
    return fb


def _frames(x: np.ndarray) -> np.ndarray:
    if x.size < _FRAME:
        x = np.pad(x, (0, _FRAME - x.size))
    n = 1 + (x.size - _FRAME) // _HOP
    idx = np.arange(_FRAME)[None, :] + _HOP * np.arange(n)[:, None]
    return x[idx] * np.hanning(_FRAME).astype(np.float32)


def _median_f0(frames: np.ndarray) -> float:
    """Autocorrelation pitch estimate, median over voiced-ish frames."""
    lag_min, lag_max = SAMPLE_RATE // _F0_MAX, SAMPLE_RATE // _F0_MIN
    f0s = []
    for fr in frames[:: max(1, len(frames) // 40)]:      # subsample: speed
        fr = fr - fr.mean()
        if np.sqrt((fr ** 2).mean()) < 1e-3:             # silence
            continue
        ac = np.correlate(fr, fr, mode="full")[len(fr) - 1:]
        window = ac[lag_min:lag_max]
        if window.size == 0 or ac[0] <= 0:
            continue
        lag = int(np.argmax(window)) + lag_min
        if ac[lag] / ac[0] > 0.3:                        # periodic enough -> voiced
            f0s.append(SAMPLE_RATE / lag)
    return float(np.median(f0s)) if f0s else 0.0


def _dct_matrix(n_coef: int, n_mels: int) -> np.ndarray:
    """DCT-II basis: log-mel -> MFCC (compact timbre descriptor)."""
    k = np.arange(n_coef)[:, None]
    n = np.arange(n_mels)[None, :]
    return np.cos(np.pi * k * (2 * n + 1) / (2 * n_mels)).astype(np.float32)


_N_MFCC = 6
_DCT = _dct_matrix(_N_MFCC + 1, _N_MELS)


def _fingerprint(seg_audio: np.ndarray, fb: np.ndarray) -> np.ndarray:
    """Speaker fingerprint: WHO is talking, not WHAT they say.

    Raw mel-band energies encode phonetic content and swamp the speaker signal, so we use:
      - median F0 + its spread (pitch — the strongest cheap speaker cue)
      - spectral centroid (voice brightness)
      - MFCC 1..6, dropping c0 (loudness) — a compact timbre descriptor
    Weighting happens in `diarize()` after z-scoring.
    """
    frames = _frames(seg_audio)
    spec = np.abs(np.fft.rfft(frames, n=_FRAME, axis=1)) ** 2
    mel = np.log(spec @ fb.T + 1e-8)

    mfcc = _DCT @ mel.mean(axis=0)               # (n_mfcc+1,)
    freqs = np.fft.rfftfreq(_FRAME, 1.0 / SAMPLE_RATE)
    power = spec.mean(axis=0)
    centroid = float((freqs * power).sum() / (power.sum() + 1e-8))

    f0 = _median_f0(frames)
    f0_spread = float(np.std([_median_f0(frames[i::3]) for i in range(3)])) if len(frames) > 6 else 0.0

    return np.concatenate(
        [[f0, f0_spread, centroid / 1000.0], mfcc[1:]]   # drop c0 (energy)
    ).astype(np.float32)


# Column weights after z-scoring: pitch dominates, timbre supports.
_WEIGHTS = np.array([4.0, 1.0, 1.0] + [0.5] * _N_MFCC, dtype=np.float32)


# --------------------------------------------------------------------------- clustering
def _kmeans2(x: np.ndarray, iters: int = 25) -> np.ndarray:
    """Tiny k-means (k=2). Init with the two most distant points (deterministic)."""
    dist = ((x[:, None, :] - x[None, :, :]) ** 2).sum(-1)
    i, j = np.unravel_index(int(np.argmax(dist)), dist.shape)
    centers = x[[i, j]].copy()

    labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        d = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        new = d.argmin(axis=1)
        if np.array_equal(new, labels):
            break
        labels = new
        for c in (0, 1):
            if np.any(labels == c):
                centers[c] = x[labels == c].mean(axis=0)
    return labels


def _smooth_short_turns(
    segments: list[dict], turns: list[list[int]], labels: np.ndarray, x: np.ndarray
) -> np.ndarray:
    """Reassign turns too short for a reliable pitch estimate.

    A ~1 s fragment ("Хорошо.", "Понятно.") yields few voiced frames, so its median F0 is noisy
    and global k-means can drop it in the wrong cluster. Deciding it LOCALLY is more reliable:
    compare its fingerprint against its immediate neighbours — same recording, same channel —
    and adopt the label of the acoustically closer one.
    """
    out = labels.copy()
    for i, turn in enumerate(turns):
        start, end = segments[turn[0]]["start"], segments[turn[-1]]["end"]
        if end - start >= _MIN_RELIABLE_TURN:
            continue

        d_prev = float(((x[i] - x[i - 1]) ** 2).sum()) if i > 0 else float("inf")
        d_next = float(((x[i] - x[i + 1]) ** 2).sum()) if i + 1 < len(turns) else float("inf")
        if d_prev == d_next == float("inf"):
            continue
        out[i] = labels[i - 1] if d_prev <= d_next else labels[i + 1]

    return out


def _assign_roles(segments: list[dict], labels: np.ndarray) -> dict[int, str]:
    """Cluster with the most operator cues -> Оператор; tie-break: whoever speaks first."""
    scores = {0: 0, 1: 0}
    for seg, lab in zip(segments, labels):
        text = seg["text"].lower()
        scores[int(lab)] += sum(cue in text for cue in _OPERATOR_CUES)

    if scores[0] != scores[1]:
        operator_cluster = 0 if scores[0] > scores[1] else 1
    else:
        operator_cluster = int(labels[0])       # the operator greets first

    return {operator_cluster: OPERATOR, 1 - operator_cluster: CLIENT}


# --------------------------------------------------------------------------- public API
def _frame_rms(waveform: np.ndarray) -> np.ndarray:
    """RMS energy per 10 ms hop — used to locate real silence in the signal."""
    n = max(1, 1 + (waveform.size - _FRAME) // _HOP)
    idx = np.arange(_FRAME)[None, :] + _HOP * np.arange(n)[:, None]
    idx = np.clip(idx, 0, waveform.size - 1)
    return np.sqrt((waveform[idx] ** 2).mean(axis=1))


def _pause_at(rms: np.ndarray, thr: float, t: float) -> bool:
    """True if a >= _TURN_PAUSE silence sits near time `t` (a speaker hand-off)."""
    half = int(0.35 / 0.010)
    c = int(t / 0.010)
    window = rms[max(0, c - half): c + half]
    if window.size == 0:
        return False
    best = run = 0
    for quiet in window < thr:
        run = run + 1 if quiet else 0
        best = max(best, run)
    return best * 0.010 >= _TURN_PAUSE


def _group_turns(segments: list[dict], waveform: np.ndarray) -> list[list[int]]:
    """Group whisper segments into speaker TURNS.

    Whisper's segment boundaries track its own decoding, not speaker changes — and with
    `vad_filter=True` it removes silence, so its timestamps come back CONTIGUOUS (gap == 0)
    even across a clear hand-off. So we ignore its gaps and look for real silence in the
    waveform around each boundary instead. Classifying whole turns also gives the pitch
    estimator far more audio than a 0.5 s fragment.
    """
    rms = _frame_rms(waveform)
    voiced = rms[rms > np.percentile(rms, 40)]
    thr = 0.15 * float(np.median(voiced)) if voiced.size else 1e-4

    turns: list[list[int]] = [[0]]
    for i in range(1, len(segments)):
        boundary = 0.5 * (segments[i - 1]["end"] + segments[i]["start"])
        if _pause_at(rms, thr, boundary):
            turns.append([i])
        else:
            turns[-1].append(i)
    return turns


def diarize(segments: list[dict], waveform: np.ndarray, *, request_id: str = "-") -> list[dict]:
    """Attach a `speaker` field (Оператор/Клиент) to each transcript segment."""
    if not segments:
        return []
    if len(segments) == 1:
        return [{**segments[0], "speaker": OPERATOR}]

    turns = _group_turns(segments, waveform)
    if len(turns) == 1:
        # No hand-off silence found — fall back to clustering each segment on its own.
        log_event(logger, "diarize_no_pauses_fallback", request_id=request_id,
                  segments=len(segments))
        turns = [[i] for i in range(len(segments))]

    fb = _mel_filterbank(_FRAME)
    feats = []
    for turn in turns:
        a = int(segments[turn[0]]["start"] * SAMPLE_RATE)
        b = int(segments[turn[-1]]["end"] * SAMPLE_RATE)
        feats.append(_fingerprint(waveform[max(0, a):max(a + _FRAME, b)], fb))

    x = np.vstack(feats)
    x = (x - x.mean(0)) / (x.std(0) + 1e-6)     # z-score per dimension
    x *= _WEIGHTS                                # pitch dominates; timbre supports
    # NB: no L2 row-normalisation — it would cancel the weighting we just applied.

    turn_labels = _kmeans2(x)
    if len(set(turn_labels.tolist())) == 1:                       # degenerate: one voice
        log_event(logger, "diarize_single_speaker", request_id=request_id, segments=len(segments))
        return [{**s, "speaker": OPERATOR} for s in segments]

    turn_labels = _smooth_short_turns(segments, turns, turn_labels, x)

    # Per-turn text so operator cues are scored on whole utterances, not fragments.
    turn_texts = [{"text": " ".join(segments[i]["text"] for i in t)} for t in turns]
    role = _assign_roles(turn_texts, turn_labels)

    out = list(segments)
    for turn, lab in zip(turns, turn_labels):
        speaker = role[int(lab)]
        for i in turn:
            out[i] = {**segments[i], "speaker": speaker}

    log_event(
        logger, "diarize_done", request_id=request_id, segments=len(out), turns=len(turns),
        operator_turns=sum(s["speaker"] == OPERATOR for s in out),
        client_turns=sum(s["speaker"] == CLIENT for s in out),
    )
    return out
