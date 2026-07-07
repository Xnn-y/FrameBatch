"""Background workers for GUI operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from framebatch.core.models import BlackFrameStatus, FrameTask
from framebatch.core.scanner import ScanResult, scan_directory
from framebatch.core.tasks import task_frame_error
from framebatch.ffmpeg.black_frame import BlackFrameChecker, BlackFrameCheckResult
from framebatch.ffmpeg.errors import FFmpegError
from framebatch.ffmpeg.probe import FFprobeVideoProber


class ScanWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, source_dir: Path, ffprobe_path: Path | None) -> None:
        super().__init__()
        self.source_dir = source_dir
        self.ffprobe_path = ffprobe_path

    @Slot()
    def run(self) -> None:
        try:
            prober = FFprobeVideoProber(self.ffprobe_path) if self.ffprobe_path else None
            result: ScanResult = scan_directory(self.source_dir, prober)
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.finished.emit(result)


class BlackFrameWorker(QObject):
    task_checked = Signal(int, object)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, tasks: list[FrameTask], ffmpeg_path: Path | None) -> None:
        super().__init__()
        self.tasks = tasks
        self.ffmpeg_path = ffmpeg_path

    @Slot()
    def run(self) -> None:
        checker = BlackFrameChecker(self.ffmpeg_path)
        try:
            for index, task in enumerate(self.tasks):
                frame_error = task_frame_error(task)
                if frame_error is not None:
                    result = BlackFrameCheckResult(
                        status=BlackFrameStatus.FAILED,
                        average_luma=None,
                        bright_pixel_ratio=None,
                        message=frame_error,
                    )
                else:
                    try:
                        result = checker.check(
                            Path(task.video.path),
                            task.config.frame_zero_based,
                        )
                    except FFmpegError as exc:
                        result = BlackFrameCheckResult(
                            status=BlackFrameStatus.FAILED,
                            average_luma=None,
                            bright_pixel_ratio=None,
                            message=exc.message,
                        )
                    except Exception as exc:
                        result = BlackFrameCheckResult(
                            status=BlackFrameStatus.FAILED,
                            average_luma=None,
                            bright_pixel_ratio=None,
                            message=f"黑屏检测失败：{exc}",
                        )
                self.task_checked.emit(index, result)
        except FFmpegError as exc:
            self.failed.emit(exc.message)
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.finished.emit()
