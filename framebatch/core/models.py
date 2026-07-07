"""Core data models shared by non-UI modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    SCANNING = "SCANNING"
    READY = "READY"
    WARNING = "WARNING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    SKIPPED = "SKIPPED"


class BlackFrameStatus(StrEnum):
    NOT_CHECKED = "NOT_CHECKED"
    CHECKING = "CHECKING"
    OK = "OK"
    SUSPECTED_BLACK = "SUSPECTED_BLACK"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class VideoFile:
    path: str
    duration_seconds: float | None = None
    frame_rate: float | None = None
    total_frames: int | None = None
    has_audio: bool = False


@dataclass(frozen=True, slots=True)
class NonVideoFile:
    path: str
    reason: str


@dataclass(slots=True)
class TaskConfig:
    frame_user_index: int
    output_stem: str | None = None

    @property
    def frame_zero_based(self) -> int:
        return self.frame_user_index - 1


@dataclass(slots=True)
class FrameTask:
    task_id: str
    video: VideoFile
    config: TaskConfig
    status: TaskStatus = TaskStatus.PENDING
    black_frame_status: BlackFrameStatus = BlackFrameStatus.NOT_CHECKED
    cover_path: str | None = None
    removed_video_path: str | None = None
    error_code: str | None = None
    message: str = ""
