"""Cover frame extraction using FFmpeg."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from framebatch.ffmpeg.cancel import CancelToken, run_cancelable
from framebatch.ffmpeg.errors import FFmpegError


DEFAULT_COVER_TIMEOUT_SECONDS = 120


@dataclass(frozen=True, slots=True)
class CoverExtractionResult:
    cover_path: Path
    message: str


class CoverExtractor:
    def __init__(
        self,
        ffmpeg_path: Path | None,
        *,
        timeout_seconds: int = DEFAULT_COVER_TIMEOUT_SECONDS,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.timeout_seconds = timeout_seconds

    def extract(
        self,
        video_path: Path,
        frame_zero_based: int,
        output_path: Path,
        *,
        overwrite: bool,
        cancel_token: CancelToken | None = None,
    ) -> CoverExtractionResult:
        if self.ffmpeg_path is None:
            raise FFmpegError("FFMPEG_NOT_FOUND", "ffmpeg 不可用，无法抽取封面。")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.ffmpeg_path),
            "-v",
            "error",
            "-y" if overwrite else "-n",
            "-i",
            str(video_path),
            "-vf",
            f"select=eq(n\\,{frame_zero_based})",
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        try:
            completed = run_cancelable(
                command,
                timeout=self.timeout_seconds,
                cancel_token=cancel_token,
            )
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError(
                "COVER_EXTRACT_TIMEOUT",
                f"封面抽取超时，已超过 {self.timeout_seconds} 秒。",
            ) from exc

        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise FFmpegError("COVER_EXTRACT_FAILED", detail or "封面抽取失败。")
        if not output_path.exists():
            raise FFmpegError("COVER_EXTRACT_FAILED", "FFmpeg 未生成封面文件。")

        return CoverExtractionResult(cover_path=output_path, message="封面抽取成功。")
