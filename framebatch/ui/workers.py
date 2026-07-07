"""Background workers for GUI operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from framebatch.core.scanner import ScanResult, scan_directory
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
