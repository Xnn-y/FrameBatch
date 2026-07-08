"""Background workers for GUI operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from framebatch.core.models import BlackFrameStatus, FrameTask
from framebatch.core.naming import (
    output_stem_for_task,
    split_output_dirs,
    task_output_paths,
    validate_cover_output,
    validate_removed_video_output,
)
from framebatch.core.scanner import ScanResult, scan_directory
from framebatch.core.tasks import task_frame_error
from framebatch.ffmpeg.black_frame import BlackFrameChecker, BlackFrameCheckResult
from framebatch.ffmpeg.cancel import CANCELED_ERROR_CODE, CANCELED_MESSAGE, CancelToken
from framebatch.ffmpeg.cover import CoverExtractor
from framebatch.ffmpeg.errors import FFmpegError
from framebatch.ffmpeg.probe import FFprobeVideoProber
from framebatch.ffmpeg.remove_frame import FrameRemovalRenderer


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


class CoverWorker(QObject):
    task_started = Signal(int)
    task_finished = Signal(int, bool, str, str, str, str)
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        tasks: list[FrameTask],
        ffmpeg_path: Path | None,
        cover_output_dir: Path,
        video_output_dir: Path,
        *,
        unified_name: str,
        overwrite: bool,
    ) -> None:
        super().__init__()
        self.tasks = tasks
        self.ffmpeg_path = ffmpeg_path
        self.cover_output_dir, self.video_output_dir = split_output_dirs(
            cover_output_dir,
            video_output_dir,
        )
        self.unified_name = unified_name
        self.overwrite = overwrite
        self.cancel_token = CancelToken()

    @Slot()
    def cancel(self) -> None:
        self.cancel_token.cancel()

    @Slot()
    def run(self) -> None:
        extractor = CoverExtractor(self.ffmpeg_path)
        renderer = FrameRemovalRenderer(self.ffmpeg_path)
        try:
            self.cover_output_dir.mkdir(parents=True, exist_ok=True)
            self.video_output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.failed.emit(f"无法创建输出目录：{exc}")
            return

        total_tasks = len(self.tasks)
        for index, task in enumerate(self.tasks):
            if self.cancel_token.is_requested():
                self.task_finished.emit(
                    index,
                    False,
                    "",
                    "",
                    "TASK_SKIPPED",
                    "已跳过：抽帧已终止。",
                )
                continue

            self.task_started.emit(index)
            frame_error = task_frame_error(task)
            if frame_error is not None:
                self.task_finished.emit(index, False, "", "", "INVALID_FRAME_INDEX", frame_error)
                continue

            task.config.output_stem = output_stem_for_task(
                task,
                index=index + 1,
                total=total_tasks,
                unified_name=self.unified_name,
            )
            output_paths = task_output_paths(task, self.cover_output_dir, self.video_output_dir)
            try:
                validate_cover_output(output_paths.cover_path, overwrite=self.overwrite)
                validate_removed_video_output(
                    output_paths.removed_video_path,
                    overwrite=self.overwrite,
                )
                result = extractor.extract(
                    Path(task.video.path),
                    task.config.frame_zero_based,
                    output_paths.cover_path,
                    overwrite=self.overwrite,
                    cancel_token=self.cancel_token,
                )
                video_result = renderer.render(
                    Path(task.video.path),
                    task.config.frame_zero_based,
                    output_paths.removed_video_path,
                    has_audio=task.video.has_audio,
                    overwrite=self.overwrite,
                    cancel_token=self.cancel_token,
                )
            except FileExistsError as exc:
                self.task_finished.emit(index, False, "", "", "OUTPUT_EXISTS", str(exc))
            except FFmpegError as exc:
                cover_path = (
                    str(output_paths.cover_path) if output_paths.cover_path.exists() else ""
                )
                message = CANCELED_MESSAGE if exc.code == CANCELED_ERROR_CODE else exc.message
                self.task_finished.emit(index, False, cover_path, "", exc.code, message)
            except Exception as exc:
                self.task_finished.emit(index, False, "", "", "UNKNOWN_ERROR", str(exc))
            else:
                self.task_finished.emit(
                    index,
                    True,
                    str(result.cover_path),
                    str(video_result.video_path),
                    "",
                    f"{result.message} {video_result.message}",
                )

        self.finished.emit()
