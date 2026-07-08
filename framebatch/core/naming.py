"""Output path naming helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
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


def split_output_dirs(cover_output_dir: Path, video_output_dir: Path) -> tuple[Path, Path]:
    if not _same_path(cover_output_dir, video_output_dir):
        return cover_output_dir, video_output_dir

    shared_output_dir = cover_output_dir
    folder_name = shared_output_dir.name.casefold()
    if folder_name == "covers":
        return shared_output_dir, shared_output_dir.parent / "videos"
    if folder_name == "videos":
        return shared_output_dir.parent / "covers", shared_output_dir
    return default_cover_output_dir(shared_output_dir), default_video_output_dir(shared_output_dir)


def output_stem_for_task(task: FrameTask, *, index: int, total: int, unified_name: str) -> str:
    normalized = normalize_output_stem(unified_name)
    if not normalized:
        return Path(task.video.path).stem
    if total == 1:
        return normalized
    return f"{normalized}_{index}"


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


def _same_path(first: Path, second: Path) -> bool:
    return _path_key(first) == _path_key(second)


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))
