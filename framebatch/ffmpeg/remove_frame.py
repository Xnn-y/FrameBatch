"""Render MP4 output with one cover image frame prepended."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from framebatch.ffmpeg.cancel import CancelToken, run_cancelable
from framebatch.ffmpeg.errors import FFmpegError


DEFAULT_PREPEND_COVER_TIMEOUT_SECONDS = 3600


@dataclass(frozen=True, slots=True)
class PrependCoverResult:
    video_path: Path
    message: str


class PrependCoverRenderer:
    def __init__(
        self,
        ffmpeg_path: Path | None,
        *,
        timeout_seconds: int = DEFAULT_PREPEND_COVER_TIMEOUT_SECONDS,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.timeout_seconds = timeout_seconds

    def render(
        self,
        video_path: Path,
        cover_image_path: Path,
        output_path: Path,
        *,
        width: int | None,
        height: int | None,
        frame_rate: float | None,
        has_audio: bool,
        overwrite: bool,
        cancel_token: CancelToken | None = None,
    ) -> PrependCoverResult:
        if self.ffmpeg_path is None:
            raise FFmpegError("FFMPEG_NOT_FOUND", "ffmpeg 不可用，无法插入封面。")
        if not cover_image_path.is_file():
            raise FFmpegError("COVER_IMAGE_NOT_FOUND", f"封面图片不存在：{cover_image_path}")

        if output_path.exists() and not overwrite:
            raise FFmpegError("OUTPUT_EXISTS", f"输出视频已存在：{output_path.name}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output_path = _partial_output_path(output_path)
        _delete_partial_output(temp_output_path)
        command = self._build_command(
            video_path,
            cover_image_path,
            temp_output_path,
            width=width,
            height=height,
            frame_rate=frame_rate,
            has_audio=has_audio,
            overwrite=True,
        )
        try:
            completed = run_cancelable(
                command,
                timeout=self.timeout_seconds,
                cancel_token=cancel_token,
            )
        except subprocess.TimeoutExpired as exc:
            _delete_partial_output(temp_output_path)
            raise FFmpegError(
                "PREPEND_COVER_TIMEOUT",
                f"插入封面超时，已超过 {self.timeout_seconds} 秒。",
            ) from exc
        except Exception:
            _delete_partial_output(temp_output_path)
            raise

        if completed.returncode != 0:
            _delete_partial_output(temp_output_path)
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise FFmpegError("PREPEND_COVER_FAILED", detail or "插入封面失败。")

        _ensure_output(temp_output_path)
        temp_output_path.replace(output_path)
        return PrependCoverResult(video_path=output_path, message="封面帧插入成功。")

    def _build_command(
        self,
        video_path: Path,
        cover_image_path: Path,
        output_path: Path,
        *,
        width: int | None,
        height: int | None,
        frame_rate: float | None,
        has_audio: bool,
        overwrite: bool,
    ) -> list[str]:
        fps = _safe_frame_rate(frame_rate)
        output_width = _even_dimension(width or 1080)
        output_height = _even_dimension(height or 1920)
        frame_duration = 1 / fps
        cover_filter = (
            f"[0:v]scale={output_width}:{output_height}:force_original_aspect_ratio=decrease,"
            f"pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,fps={_format_float(fps)},format=yuv420p,"
            f"trim=duration={_format_float(frame_duration)},setpts=PTS-STARTPTS[cover]"
        )
        video_filter = (
            f"[1:v]scale={output_width}:{output_height}:force_original_aspect_ratio=decrease,"
            f"pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1,fps={_format_float(fps)},format=yuv420p,setpts=PTS-STARTPTS[video]"
        )
        concat_filter = "[cover][video]concat=n=2:v=1:a=0[v]"
        command = [
            str(self.ffmpeg_path),
            "-v",
            "error",
            "-y" if overwrite else "-n",
            "-loop",
            "1",
            "-framerate",
            _format_float(fps),
            "-i",
            str(cover_image_path),
            "-i",
            str(video_path),
            "-filter_complex",
            f"{cover_filter};{video_filter};{concat_filter}",
            "-map",
            "[v]",
        ]
        if has_audio:
            command.extend(["-map", "1:a?", "-c:a", "copy"])
        else:
            command.append("-an")
        command.extend(
            [
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
                str(output_path),
            ]
        )
        return command


FrameRemovalRenderer = PrependCoverRenderer
RemoveFrameResult = PrependCoverResult


def _safe_frame_rate(value: float | None) -> float:
    if value is None or value <= 0:
        return 30.0
    return value


def _format_float(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _even_dimension(value: int) -> int:
    if value <= 1:
        return 2
    if value % 2 == 0:
        return value
    return value - 1


def _ensure_output(output_path: Path) -> None:
    if not output_path.exists():
        raise FFmpegError("PREPEND_COVER_FAILED", "FFmpeg 未生成输出视频文件。")


def _partial_output_path(output_path: Path) -> Path:
    return output_path.with_name(f".{output_path.stem}.partial{output_path.suffix}")


def _delete_partial_output(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
