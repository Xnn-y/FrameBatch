"""Render MP4 output with one target frame removed."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from framebatch.ffmpeg.errors import FFmpegError


DEFAULT_REMOVE_FRAME_TIMEOUT_SECONDS = 3600


@dataclass(frozen=True, slots=True)
class RemoveFrameResult:
    video_path: Path
    message: str


class FrameRemovalRenderer:
    def __init__(
        self,
        ffmpeg_path: Path | None,
        *,
        timeout_seconds: int = DEFAULT_REMOVE_FRAME_TIMEOUT_SECONDS,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.timeout_seconds = timeout_seconds

    def render(
        self,
        video_path: Path,
        frame_zero_based: int,
        output_path: Path,
        *,
        has_audio: bool,
        overwrite: bool,
    ) -> RemoveFrameResult:
        if self.ffmpeg_path is None:
            raise FFmpegError("FFMPEG_NOT_FOUND", "ffmpeg 不可用，无法生成去帧视频。")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = self._build_command(
            video_path,
            frame_zero_based,
            output_path,
            has_audio=has_audio,
            overwrite=overwrite,
            audio_mode="copy",
        )
        completed = self._run(command)
        if completed.returncode != 0 and has_audio:
            fallback = self._build_command(
                video_path,
                frame_zero_based,
                output_path,
                has_audio=has_audio,
                overwrite=True,
                audio_mode="aac",
            )
            completed = self._run(fallback)
            if completed.returncode == 0:
                _ensure_output(output_path)
                return RemoveFrameResult(
                    video_path=output_path,
                    message="去帧视频生成成功；音频已降级为 AAC 重编码。",
                )

        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise FFmpegError("VIDEO_RENDER_FAILED", detail or "去帧视频生成失败。")

        _ensure_output(output_path)
        return RemoveFrameResult(video_path=output_path, message="去帧视频生成成功。")

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError(
                "VIDEO_RENDER_TIMEOUT",
                f"去帧视频生成超时，已超过 {self.timeout_seconds} 秒。",
            ) from exc

    def _build_command(
        self,
        video_path: Path,
        frame_zero_based: int,
        output_path: Path,
        *,
        has_audio: bool,
        overwrite: bool,
        audio_mode: str,
    ) -> list[str]:
        command = [
            str(self.ffmpeg_path),
            "-v",
            "error",
            "-y" if overwrite else "-n",
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-vf",
            f"select=not(eq(n\\,{frame_zero_based})),setpts=N/FRAME_RATE/TB",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
        if has_audio:
            command.extend(["-map", "0:a?"])
            if audio_mode == "aac":
                command.extend(["-c:a", "aac", "-b:a", "192k"])
            else:
                command.extend(["-c:a", "copy"])
        else:
            command.append("-an")
        command.append(str(output_path))
        return command


def _ensure_output(output_path: Path) -> None:
    if not output_path.exists():
        raise FFmpegError("VIDEO_RENDER_FAILED", "FFmpeg 未生成去帧视频文件。")
