"""Locate FFmpeg and ffprobe executables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


FFMPEG_EXE = "ffmpeg.exe"
FFPROBE_EXE = "ffprobe.exe"


@dataclass(frozen=True, slots=True)
class FFmpegLocation:
    ffmpeg_path: Path | None
    ffprobe_path: Path | None
    source: str
    message: str

    @property
    def is_available(self) -> bool:
        return self.ffmpeg_path is not None and self.ffprobe_path is not None


def locate_ffmpeg(
    *,
    configured_ffmpeg_path: str | None = None,
    app_root: Path | None = None,
) -> FFmpegLocation:
    configured = _from_configured_path(configured_ffmpeg_path)
    if configured.is_available:
        return configured

    bundled = _from_bundled_path(app_root or Path.cwd())
    if bundled.is_available:
        return bundled

    system = _from_system_path()
    if system.is_available:
        return system

    return FFmpegLocation(
        ffmpeg_path=None,
        ffprobe_path=None,
        source="missing",
        message="FFmpeg 不可用。请先配置 ffmpeg.exe，才能精确识别视频文件。",
    )


def _from_configured_path(configured_ffmpeg_path: str | None) -> FFmpegLocation:
    if not configured_ffmpeg_path:
        return FFmpegLocation(None, None, "configured", "尚未配置 FFmpeg 路径。")

    ffmpeg_path = Path(configured_ffmpeg_path)
    if ffmpeg_path.is_dir():
        ffmpeg_path = ffmpeg_path / FFMPEG_EXE
    ffprobe_path = ffmpeg_path.with_name(FFPROBE_EXE)

    if ffmpeg_path.is_file() and ffprobe_path.is_file():
        return FFmpegLocation(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            source="configured",
            message=f"正在使用已配置的 FFmpeg：{ffmpeg_path}",
        )

    return FFmpegLocation(
        ffmpeg_path=None,
        ffprobe_path=None,
        source="configured",
        message="已配置的 FFmpeg 路径不完整，请确认 ffmpeg.exe 与 ffprobe.exe 在同一目录。",
    )


def _from_bundled_path(app_root: Path) -> FFmpegLocation:
    bin_dir = app_root / "tools" / "ffmpeg" / "bin"
    ffmpeg_path = bin_dir / FFMPEG_EXE
    ffprobe_path = bin_dir / FFPROBE_EXE

    if ffmpeg_path.is_file() and ffprobe_path.is_file():
        return FFmpegLocation(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            source="bundled",
            message=f"正在使用内置 FFmpeg：{ffmpeg_path}",
        )

    return FFmpegLocation(None, None, "bundled", "未找到内置 FFmpeg。")


def _from_system_path() -> FFmpegLocation:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    if ffmpeg and ffprobe:
        return FFmpegLocation(
            ffmpeg_path=Path(ffmpeg),
            ffprobe_path=Path(ffprobe),
            source="path",
            message=f"正在使用系统 PATH 中的 FFmpeg：{ffmpeg}",
        )

    return FFmpegLocation(None, None, "path", "系统 PATH 中未找到 FFmpeg。")
