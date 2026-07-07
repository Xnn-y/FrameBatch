"""Error types for FFmpeg integration."""

from __future__ import annotations


class FFmpegError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class FFprobeUnavailableError(FFmpegError):
    def __init__(self) -> None:
        super().__init__("FFPROBE_NOT_FOUND", "ffprobe 不可用。")


class ProbeFailedError(FFmpegError):
    def __init__(self, message: str) -> None:
        super().__init__("FFPROBE_FAILED", message)
