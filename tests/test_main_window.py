import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from framebatch.config.settings import SettingsStore
from framebatch.core.models import NonVideoFile, VideoFile
from framebatch.core.scanner import ScanResult
from framebatch.core.tasks import create_frame_tasks
from framebatch.ui.main_window import MainWindow


def _app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication(sys.argv)


def test_open_output_dir_button_follows_output_text(tmp_path: Path) -> None:
    _app()
    settings = SettingsStore.load(tmp_path / "settings.json")
    window = MainWindow(settings)

    window.output_edit.clear()
    window._refresh_history_actions()

    assert window.open_output_dir_button.isEnabled() is False

    window.output_edit.setText(str(tmp_path / "videos"))

    assert window.open_output_dir_button.isEnabled() is True

    window.history_table.clearSelection()
    window._refresh_history_actions()

    assert window.open_output_dir_button.isEnabled() is True


def test_process_button_uses_auto_detected_or_manual_cover_image(tmp_path: Path) -> None:
    _app()
    settings = SettingsStore.load(tmp_path / "settings.json")
    window = MainWindow(settings)
    window.ffmpeg_location = window.ffmpeg_location.__class__(
        ffmpeg_path=tmp_path / "ffmpeg.exe",
        ffprobe_path=tmp_path / "ffprobe.exe",
        source="test",
        message="ok",
    )
    video = VideoFile(path=str(tmp_path / "episode01.mp4"))

    window.scan_result = ScanResult(
        source_dir=tmp_path,
        videos=[video],
        cover_images=[NonVideoFile(path=str(tmp_path / "cover.jpg"), reason="封面图片候选。")],
        candidate_videos=[],
        non_videos=[],
    )
    window._refresh_detected_cover_image()
    window.tasks = create_frame_tasks([video], 1)
    window._refresh_task_actions()

    assert window.cover_image_edit.text().endswith("cover.jpg")
    assert window.process_button.isEnabled() is True

    window.cover_image_edit.clear()
    window.scan_result = ScanResult(
        source_dir=tmp_path,
        videos=[video],
        cover_images=[
            NonVideoFile(path=str(tmp_path / "cover.jpg"), reason="封面图片候选。"),
            NonVideoFile(path=str(tmp_path / "poster.png"), reason="封面图片候选。"),
        ],
        candidate_videos=[],
        non_videos=[],
    )
    window._refresh_detected_cover_image()
    window._refresh_task_actions()

    assert window.cover_image_edit.text() == ""
    assert window.process_button.isEnabled() is False

    window.cover_image_edit.setText(str(tmp_path / "manual.jpg"))

    assert window.process_button.isEnabled() is True
