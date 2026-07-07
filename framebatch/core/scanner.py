"""Directory scanning and video classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from framebatch.core.models import NonVideoFile, VideoFile
from framebatch.ffmpeg.errors import FFmpegError


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".flv",
    ".wmv",
    ".webm",
    ".m4v",
    ".ts",
    ".mts",
    ".m2ts",
}


class VideoProber(Protocol):
    def probe(self, path: Path) -> VideoFile:
        ...


@dataclass(frozen=True, slots=True)
class ScanResult:
    source_dir: Path
    videos: list[VideoFile]
    non_videos: list[NonVideoFile]

    @property
    def total_files(self) -> int:
        return len(self.videos) + len(self.non_videos)


def scan_directory(source_dir: Path, prober: VideoProber | None) -> ScanResult:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {source_dir}")

    videos: list[VideoFile] = []
    non_videos: list[NonVideoFile] = []

    for path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            non_videos.append(
                NonVideoFile(path=str(path), reason="文件扩展名不是视频候选格式。")
            )
            continue

        if prober is None:
            non_videos.append(
                NonVideoFile(path=str(path), reason="ffprobe 不可用，无法确认该文件是否为有效视频。")
            )
            continue

        try:
            videos.append(prober.probe(path))
        except FFmpegError as exc:
            non_videos.append(NonVideoFile(path=str(path), reason=exc.message))

    return ScanResult(source_dir=source_dir, videos=videos, non_videos=non_videos)
