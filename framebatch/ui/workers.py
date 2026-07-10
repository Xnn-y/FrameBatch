"""Background workers for GUI operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from framebatch.core.models import FrameTask
from framebatch.core.naming import (
    output_stem_for_task,
    task_output_paths,
    validate_video_output,
)
from framebatch.core.scanner import ScanResult, scan_directory
from framebatch.ffmpeg.cancel import CANCELED_ERROR_CODE, CANCELED_MESSAGE, CancelToken
from framebatch.ffmpeg.errors import FFmpegError
from framebatch.ffmpeg.probe import FFprobeVideoProber
from framebatch.ffmpeg.remove_frame import PrependCoverRenderer


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


class CoverWorker(QObject):
    task_started = Signal(int)
    task_finished = Signal(int, bool, str, str, str, str)
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        tasks: list[FrameTask],
        ffmpeg_path: Path | None,
        cover_image_path: Path,
        output_dir: Path,
        *,
        unified_name: str,
        overwrite: bool,
    ) -> None:
        super().__init__()
        self.tasks = tasks
        self.ffmpeg_path = ffmpeg_path
        self.cover_image_path = cover_image_path
        self.output_dir = output_dir
        self.unified_name = unified_name
        self.overwrite = overwrite
        self.cancel_token = CancelToken()

    @Slot()
    def cancel(self) -> None:
        self.cancel_token.cancel()

    @Slot()
    def run(self) -> None:
        renderer = PrependCoverRenderer(self.ffmpeg_path)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self.failed.emit(f"无法创建输出目录：{exc}")
            return
        if not self.cover_image_path.is_file():
            self.failed.emit(f"封面图片不存在：{self.cover_image_path}")
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
                    "已跳过：处理已终止。",
                )
                continue

            self.task_started.emit(index)
            task.config.output_stem = output_stem_for_task(
                task,
                index=index + 1,
                total=total_tasks,
                unified_name=self.unified_name,
            )
            output_paths = task_output_paths(task, self.output_dir)
            try:
                validate_video_output(output_paths.video_path, overwrite=self.overwrite)
                result = renderer.render(
                    Path(task.video.path),
                    self.cover_image_path,
                    output_paths.video_path,
                    width=task.video.width,
                    height=task.video.height,
                    frame_rate=task.video.frame_rate,
                    has_audio=task.video.has_audio,
                    overwrite=self.overwrite,
                    cancel_token=self.cancel_token,
                )
            except FileExistsError as exc:
                self.task_finished.emit(index, False, "", "", "OUTPUT_EXISTS", str(exc))
            except FFmpegError as exc:
                message = CANCELED_MESSAGE if exc.code == CANCELED_ERROR_CODE else exc.message
                output_path = str(output_paths.video_path) if output_paths.video_path.exists() else ""
                self.task_finished.emit(index, False, "", output_path, exc.code, message)
            except Exception as exc:
                self.task_finished.emit(index, False, "", "", "UNKNOWN_ERROR", str(exc))
            else:
                self.task_finished.emit(
                    index,
                    True,
                    str(self.cover_image_path),
                    str(result.video_path),
                    "",
                    result.message,
                )

        self.finished.emit()
