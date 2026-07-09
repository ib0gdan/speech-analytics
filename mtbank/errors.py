"""Domain errors surfaced to the user (chat markdown / REST 4xx) — ASR-05."""

from __future__ import annotations


class AnalysisError(Exception):
    """Any user-facing failure in the audio -> analysis flow.

    `message` is safe to show to the end user (Russian, actionable).
    """

    def __init__(self, message: str, *, code: str = "analysis_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class AudioFetchError(AnalysisError):
    def __init__(self, message: str):
        super().__init__(message, code="audio_fetch_error")


class AudioDecodeError(AnalysisError):
    def __init__(self, message: str):
        super().__init__(message, code="audio_decode_error")


class EmptyAudioError(AnalysisError):
    def __init__(self, message: str = "Аудио пустое или не содержит распознаваемой речи."):
        super().__init__(message, code="empty_audio")
