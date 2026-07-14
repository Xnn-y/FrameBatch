"""Output path naming helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import re

from framebatch.core.models import FrameTask

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')


@dataclass(frozen=True, slots=True)
class TaskOutputPaths:
    video_path: Path


def default_video_output_dir(source_dir: Path) -> Path:
    return source_dir / "videos"


def default_cover_output_dir(source_dir: Path) -> Path:
    return default_video_output_dir(source_dir)


def default_output_dir(source_dir: Path) -> Path:
    return default_video_output_dir(source_dir)


def task_output_paths(task: FrameTask, output_dir: Path) -> TaskOutputPaths:
    stem = task.config.output_stem or source_stem(task.video.path)
    return TaskOutputPaths(video_path=output_dir / f"{stem}.mp4")


def split_output_dirs(cover_output_dir: Path, video_output_dir: Path) -> tuple[Path, Path]:
    return video_output_dir, video_output_dir


def output_stem_for_task(task: FrameTask, *, index: int, total: int, unified_name: str) -> str:
    normalized = normalize_output_stem(unified_name)
    if not normalized:
        return source_stem(task.video.path)
    if total == 1:
        return normalized
    return f"{normalized}_{index}"


def source_stem(path: str) -> str:
    if "\\" in path or PureWindowsPath(path).drive:
        return PureWindowsPath(path).stem
    return Path(path).stem


def normalize_output_stem(value: str | None) -> str:
    if value is None:
        return ""
    normalized = INVALID_FILENAME_CHARS.sub("_", value.strip())
    return normalized.rstrip(" .")


def validate_video_output(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"输出视频已存在：{path.name}")


def validate_cover_output(path: Path, *, overwrite: bool) -> None:
    validate_video_output(path, overwrite=overwrite)


def validate_removed_video_output(path: Path, *, overwrite: bool) -> None:
    validate_video_output(path, overwrite=overwrite)
