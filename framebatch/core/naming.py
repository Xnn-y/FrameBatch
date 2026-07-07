"""Output path naming helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from framebatch.core.models import FrameTask

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')


@dataclass(frozen=True, slots=True)
class TaskOutputPaths:
    cover_path: Path
    removed_video_path: Path


def default_cover_output_dir(source_dir: Path) -> Path:
    return source_dir / "covers"


def default_video_output_dir(source_dir: Path) -> Path:
    return source_dir / "videos"


def default_output_dir(source_dir: Path) -> Path:
    return default_cover_output_dir(source_dir)


def task_output_paths(
    task: FrameTask,
    cover_output_dir: Path,
    video_output_dir: Path,
) -> TaskOutputPaths:
    stem = task.config.output_stem or Path(task.video.path).stem
    return TaskOutputPaths(
        cover_path=cover_output_dir / f"{stem}.jpg",
        removed_video_path=video_output_dir / f"{stem}.mp4",
    )


def output_stem_for_task(task: FrameTask, *, index: int, total: int, unified_name: str) -> str:
    normalized = normalize_output_stem(unified_name)
    if not normalized:
        return Path(task.video.path).stem
    if total == 1:
        return normalized
    return f"{normalized}_{index:04d}"


def normalize_output_stem(value: str | None) -> str:
    if value is None:
        return ""
    normalized = INVALID_FILENAME_CHARS.sub("_", value.strip())
    return normalized.rstrip(" .")


def validate_cover_output(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"封面文件已存在：{path.name}")


def validate_removed_video_output(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"去帧视频已存在：{path.name}")
