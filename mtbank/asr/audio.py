"""Audio acquisition + decoding (ASR-02, ASR-05).

Accepts a URL, a local path, or raw bytes; hands back a local file path and a decoded
16 kHz mono waveform. Format support (WAV/MP3/OGG/M4A/FLAC) comes from ffmpeg via PyAV,
which faster-whisper already depends on — no extra dependency.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import requests

from ..errors import AudioDecodeError, AudioFetchError

SAMPLE_RATE = 16_000
_MAX_BYTES = 200 * 1024 * 1024          # 200 MB guard
_DOWNLOAD_TIMEOUT = 30


def fetch_audio(source: str | bytes, *, filename: str | None = None) -> Path:
    """Return a local path for `source` (URL, existing path, or raw bytes)."""
    if isinstance(source, (bytes, bytearray)):
        if not source:
            raise AudioFetchError("Загруженный файл пустой.")
        return _write_temp(bytes(source), suffix=Path(filename or "audio.wav").suffix or ".wav")

    if source.startswith(("http://", "https://")):
        return _download(source)

    path = Path(source)
    if not path.is_file():
        raise AudioFetchError(f"Файл не найден: {source}")
    if path.stat().st_size == 0:
        raise AudioFetchError(f"Файл пустой: {source}")
    return path


def _download(url: str) -> Path:
    try:
        resp = requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise AudioFetchError(f"Не удалось скачать аудио по ссылке: {e}") from e

    suffix = Path(url.split("?")[0]).suffix or ".audio"
    chunks, total = [], 0
    for chunk in resp.iter_content(chunk_size=1 << 16):
        total += len(chunk)
        if total > _MAX_BYTES:
            raise AudioFetchError("Файл слишком большой (>200 МБ).")
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        raise AudioFetchError("По ссылке нет данных (пустой ответ).")
    return _write_temp(data, suffix=suffix)


def _write_temp(data: bytes, *, suffix: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


def decode_waveform(path: Path) -> np.ndarray:
    """Decode any ffmpeg-supported audio into 16 kHz mono float32."""
    from faster_whisper.audio import decode_audio  # imported lazily: heavy dep

    try:
        audio = decode_audio(str(path), sampling_rate=SAMPLE_RATE)
    except Exception as e:  # noqa: BLE001 — PyAV raises many concrete types
        raise AudioDecodeError(
            "Не удалось декодировать аудио. Поддерживаются WAV, MP3, OGG, M4A, FLAC."
        ) from e

    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        raise AudioDecodeError("Аудиодорожка пустая.")
    return audio
