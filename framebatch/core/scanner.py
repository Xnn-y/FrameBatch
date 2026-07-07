"""Directory scanning and video classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import re

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

EPISODE_PATTERNS = [
    re.compile(r"第\s*([0-9０-９]+)\s*[集话話期]", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9])(?:ep|episode|e)\s*0*([0-9０-９]+)(?![a-z0-9])", re.IGNORECASE),
]


class VideoProber(Protocol):
    def probe(self, path: Path) -> VideoFile:
        ...


@dataclass(frozen=True, slots=True)
class ScanResult:
    source_dir: Path
    videos: list[VideoFile]
    candidate_videos: list[NonVideoFile]
    non_videos: list[NonVideoFile]

    @property
    def total_files(self) -> int:
        return len(self.videos) + len(self.candidate_videos) + len(self.non_videos)


def scan_directory(source_dir: Path, prober: VideoProber | None) -> ScanResult:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {source_dir}")

    videos: list[VideoFile] = []
    candidate_videos: list[NonVideoFile] = []
    non_videos: list[NonVideoFile] = []

    for path in sorted(source_dir.iterdir(), key=_sort_key_for_path):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            non_videos.append(
                NonVideoFile(path=str(path), reason="文件扩展名不是视频候选格式。")
            )
            continue

        if prober is None:
            candidate_videos.append(
                NonVideoFile(path=str(path), reason="ffprobe 不可用，无法确认该文件是否为有效视频。")
            )
            continue

        try:
            videos.append(prober.probe(path))
        except FFmpegError as exc:
            candidate_videos.append(NonVideoFile(path=str(path), reason=exc.message))

    return ScanResult(
        source_dir=source_dir,
        videos=videos,
        candidate_videos=candidate_videos,
        non_videos=non_videos,
    )


NaturalKey = tuple[tuple[int, object], ...]


def _sort_key_for_path(path: Path) -> tuple[NaturalKey, int, NaturalKey]:
    episode = _extract_episode(path.stem)
    natural_name = _natural_key(path.name)
    if episode is None:
        return natural_name, 1_000_000_000, natural_name

    episode_number, start, end = episode
    series_name = f"{path.stem[:start]}{path.stem[end:]}"
    return _natural_key(series_name), episode_number, natural_name


def _extract_episode(name: str) -> tuple[int, int, int] | None:
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(name)
        if match:
            return _parse_digits(match.group(1)), match.start(), match.end()
    return None


def _natural_key(value: str) -> NaturalKey:
    normalized = _normalize_digits(value.casefold())
    parts = re.split(r"([0-9]+)", normalized)
    return tuple((1, int(part)) if part.isdigit() else (0, part) for part in parts if part)


def _parse_digits(value: str) -> int:
    return int(_normalize_digits(value))


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
