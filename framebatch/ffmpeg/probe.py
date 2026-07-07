"""Video metadata probing through ffprobe."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import json
import subprocess

from framebatch.core.models import VideoFile
from framebatch.ffmpeg.errors import FFprobeUnavailableError, ProbeFailedError


class FFprobeVideoProber:
    def __init__(self, ffprobe_path: Path | None) -> None:
        self.ffprobe_path = ffprobe_path

    def probe(self, path: Path) -> VideoFile:
        if self.ffprobe_path is None:
            raise FFprobeUnavailableError()

        command = [
            str(self.ffprobe_path),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "ffprobe 读取文件失败。"
            raise ProbeFailedError(detail)

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProbeFailedError("ffprobe 返回了无效 JSON。") from exc

        streams = payload.get("streams", [])
        video_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        if video_stream is None:
            raise ProbeFailedError("未检测到视频流。")

        audio_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )
        duration = _parse_duration(video_stream, payload.get("format", {}))
        frame_rate = _parse_frame_rate(video_stream)
        total_frames = _parse_total_frames(video_stream, duration, frame_rate)

        return VideoFile(
            path=str(path),
            duration_seconds=duration,
            frame_rate=frame_rate,
            total_frames=total_frames,
            has_audio=audio_stream is not None,
        )


def _parse_duration(video_stream: dict, format_info: dict) -> float | None:
    raw = video_stream.get("duration") or format_info.get("duration")
    if raw in (None, "N/A"):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_frame_rate(video_stream: dict) -> float | None:
    raw = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    if not raw or raw == "0/0":
        return None
    try:
        return float(Fraction(raw))
    except (ValueError, ZeroDivisionError):
        return None


def _parse_total_frames(
    video_stream: dict,
    duration: float | None,
    frame_rate: float | None,
) -> int | None:
    raw = video_stream.get("nb_frames")
    if raw not in (None, "N/A"):
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass

    if duration is None or frame_rate is None:
        return None
    return max(1, round(duration * frame_rate))
