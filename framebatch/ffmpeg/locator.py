"""Locate FFmpeg and ffprobe executables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys


FFMPEG_NAME = "ffmpeg"
FFPROBE_NAME = "ffprobe"
WINDOWS_EXECUTABLE_SUFFIX = ".exe"


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

    for root in _candidate_app_roots(app_root):
        bundled = _from_bundled_path(root)
        if bundled.is_available:
            return bundled

    system = _from_system_path()
    if system.is_available:
        return system

    return FFmpegLocation(
        ffmpeg_path=None,
        ffprobe_path=None,
        source="missing",
        message="FFmpeg 不可用。请先配置 ffmpeg，才能精确识别视频文件。",
    )


def _from_configured_path(configured_ffmpeg_path: str | None) -> FFmpegLocation:
    if not configured_ffmpeg_path:
        return FFmpegLocation(None, None, "configured", "尚未配置 FFmpeg 路径。")

    configured_path = Path(configured_ffmpeg_path)
    ffmpeg_path, ffprobe_path = _resolve_ffmpeg_pair(configured_path)

    if ffmpeg_path is not None and ffprobe_path is not None:
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
        message="已配置的 FFmpeg 路径不完整，请确认 ffmpeg 与 ffprobe 在同一目录。",
    )


def _from_bundled_path(app_root: Path) -> FFmpegLocation:
    candidate_dirs = [
        app_root / "tools" / "ffmpeg",
        app_root / "tools" / "ffmpeg" / "bin",
        app_root / "_internal" / "tools" / "ffmpeg",
        app_root / "_internal" / "tools" / "ffmpeg" / "bin",
    ]

    for bin_dir in candidate_dirs:
        ffmpeg_path, ffprobe_path = _resolve_ffmpeg_pair(bin_dir)
        if ffmpeg_path is not None and ffprobe_path is not None:
            return FFmpegLocation(
                ffmpeg_path=ffmpeg_path,
                ffprobe_path=ffprobe_path,
                source="bundled",
                message=f"正在使用内置 FFmpeg：{ffmpeg_path}",
            )

    return FFmpegLocation(None, None, "bundled", "未找到内置 FFmpeg。")


def _candidate_app_roots(app_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    if app_root is not None:
        roots.append(app_root)

    pyinstaller_root = getattr(sys, "_MEIPASS", None)
    if pyinstaller_root:
        roots.append(Path(pyinstaller_root))

    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)

    roots.append(Path.cwd())

    unique_roots: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            unique_roots.append(resolved)
            seen.add(resolved)
    return unique_roots


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


def _resolve_ffmpeg_pair(path: Path) -> tuple[Path | None, Path | None]:
    if path.is_dir():
        for ffmpeg_name, ffprobe_name in _executable_name_pairs():
            ffmpeg_path = path / ffmpeg_name
            ffprobe_path = path / ffprobe_name
            if ffmpeg_path.is_file() and ffprobe_path.is_file():
                return ffmpeg_path, ffprobe_path
        return None, None

    if not path.is_file():
        return None, None

    ffprobe_path = path.with_name(_ffprobe_name_for(path.name))
    if ffprobe_path.is_file():
        return path, ffprobe_path
    return None, None


def _executable_name_pairs() -> list[tuple[str, str]]:
    if sys.platform.startswith("win"):
        return [
            (f"{FFMPEG_NAME}{WINDOWS_EXECUTABLE_SUFFIX}", f"{FFPROBE_NAME}{WINDOWS_EXECUTABLE_SUFFIX}"),
            (FFMPEG_NAME, FFPROBE_NAME),
        ]
    return [
        (FFMPEG_NAME, FFPROBE_NAME),
        (f"{FFMPEG_NAME}{WINDOWS_EXECUTABLE_SUFFIX}", f"{FFPROBE_NAME}{WINDOWS_EXECUTABLE_SUFFIX}"),
    ]


def _ffprobe_name_for(ffmpeg_name: str) -> str:
    if ffmpeg_name.lower().endswith(WINDOWS_EXECUTABLE_SUFFIX):
        return f"{FFPROBE_NAME}{WINDOWS_EXECUTABLE_SUFFIX}"
    return FFPROBE_NAME
