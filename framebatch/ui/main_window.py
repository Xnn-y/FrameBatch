"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from framebatch.config.settings import SettingsStore
from framebatch.core.models import NonVideoFile, VideoFile
from framebatch.core.scanner import ScanResult
from framebatch.ffmpeg.locator import FFmpegLocation, locate_ffmpeg
from framebatch.ui.workers import ScanWorker


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self.settings = settings
        self.ffmpeg_location: FFmpegLocation = locate_ffmpeg(
            configured_ffmpeg_path=self.settings.settings.ffmpeg_path
        )
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None

        self.setWindowTitle("FrameBatch")
        self.resize(1180, 760)
        self.setStatusBar(QStatusBar(self))

        self.input_edit = QLineEdit(self.settings.settings.last_input_dir or "")
        self.input_edit.setPlaceholderText("选择包含视频和其他文件的目录")
        self.browse_input_button = QPushButton("浏览")
        self.scan_button = QPushButton("扫描")

        self.ffmpeg_edit = QLineEdit(self.settings.settings.ffmpeg_path or "")
        self.ffmpeg_edit.setPlaceholderText("可选：选择 ffmpeg.exe")
        self.browse_ffmpeg_button = QPushButton("浏览")
        self.refresh_ffmpeg_button = QPushButton("重新检测")
        self.ffmpeg_status_label = QLabel()

        self.summary_label = QLabel("尚未扫描目录。")
        self.video_table = self._create_table(
            ["文件", "时长", "帧率", "总帧数", "音频", "路径"]
        )
        self.non_video_table = self._create_table(["文件", "原因", "路径"])

        self._build_layout()
        self._connect_signals()
        self._apply_styles()
        self._refresh_ffmpeg_status(save=False)

    def _build_layout(self) -> None:
        input_group = QGroupBox("输入目录")
        input_layout = QGridLayout(input_group)
        input_layout.addWidget(QLabel("目录"), 0, 0)
        input_layout.addWidget(self.input_edit, 0, 1)
        input_layout.addWidget(self.browse_input_button, 0, 2)
        input_layout.addWidget(self.scan_button, 0, 3)

        ffmpeg_group = QGroupBox("FFmpeg")
        ffmpeg_layout = QGridLayout(ffmpeg_group)
        ffmpeg_layout.addWidget(QLabel("ffmpeg.exe"), 0, 0)
        ffmpeg_layout.addWidget(self.ffmpeg_edit, 0, 1)
        ffmpeg_layout.addWidget(self.browse_ffmpeg_button, 0, 2)
        ffmpeg_layout.addWidget(self.refresh_ffmpeg_button, 0, 3)
        ffmpeg_layout.addWidget(self.ffmpeg_status_label, 1, 0, 1, 4)

        tables_layout = QHBoxLayout()

        video_group = QGroupBox("已确认视频")
        video_layout = QVBoxLayout(video_group)
        video_layout.addWidget(self.video_table)

        non_video_group = QGroupBox("其他文件 / 未确认")
        non_video_layout = QVBoxLayout(non_video_group)
        non_video_layout.addWidget(self.non_video_table)

        tables_layout.addWidget(video_group, 3)
        tables_layout.addWidget(non_video_group, 2)

        root_layout = QVBoxLayout()
        root_layout.addWidget(input_group)
        root_layout.addWidget(ffmpeg_group)
        root_layout.addWidget(self.summary_label)
        root_layout.addLayout(tables_layout, 1)

        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.browse_input_button.clicked.connect(self._choose_input_dir)
        self.browse_ffmpeg_button.clicked.connect(self._choose_ffmpeg)
        self.refresh_ffmpeg_button.clicked.connect(lambda: self._refresh_ffmpeg_status(save=True))
        self.scan_button.clicked.connect(self._start_scan)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f6f7f9;
            }
            QGroupBox {
                font-weight: 600;
                border: 1px solid #d5dae1;
                border-radius: 6px;
                margin-top: 12px;
                padding: 12px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLineEdit {
                min-height: 28px;
                padding: 2px 8px;
            }
            QPushButton {
                min-height: 30px;
                padding: 4px 12px;
            }
            QTableWidget {
                background: #ffffff;
                gridline-color: #e1e5eb;
                selection-background-color: #dbeafe;
            }
            QLabel#statusOk {
                color: #166534;
            }
            QLabel#statusError {
                color: #b91c1c;
            }
            """
        )

    def _create_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        return table

    @Slot()
    def _choose_input_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输入目录", self.input_edit.text())
        if not directory:
            return
        self.input_edit.setText(directory)

    @Slot()
    def _choose_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 ffmpeg.exe",
            self.ffmpeg_edit.text(),
            "FFmpeg 可执行文件 (ffmpeg.exe);;所有文件 (*)",
        )
        if not path:
            return
        self.ffmpeg_edit.setText(path)
        self.settings.update(ffmpeg_path=path)
        self.settings.save()
        self._refresh_ffmpeg_status(save=True)

    def _refresh_ffmpeg_status(self, *, save: bool) -> None:
        configured_path = self.ffmpeg_edit.text().strip() or None
        self.ffmpeg_location = locate_ffmpeg(configured_ffmpeg_path=configured_path)
        if save:
            self.settings.update(
                ffmpeg_path=(
                    str(self.ffmpeg_location.ffmpeg_path)
                    if self.ffmpeg_location.ffmpeg_path
                    else configured_path
                ),
                ffprobe_path=(
                    str(self.ffmpeg_location.ffprobe_path)
                    if self.ffmpeg_location.ffprobe_path
                    else None
                ),
            )
            self.settings.save()
        if self.ffmpeg_location.is_available:
            self.ffmpeg_status_label.setObjectName("statusOk")
            self.ffmpeg_status_label.setText(self.ffmpeg_location.message)
        else:
            self.ffmpeg_status_label.setObjectName("statusError")
            self.ffmpeg_status_label.setText(self.ffmpeg_location.message)
        self.ffmpeg_status_label.style().unpolish(self.ffmpeg_status_label)
        self.ffmpeg_status_label.style().polish(self.ffmpeg_status_label)

    @Slot()
    def _start_scan(self) -> None:
        source_text = self.input_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, "需要输入目录", "请先选择输入目录，再开始扫描。")
            return

        source_dir = Path(source_text)
        if not source_dir.is_dir():
            QMessageBox.warning(self, "目录不存在", f"输入目录不存在：\n{source_dir}")
            return

        self.settings.update(last_input_dir=str(source_dir))
        self.settings.save()
        self._set_scanning_enabled(False)
        self._clear_tables()
        self.summary_label.setText("正在扫描...")
        self.statusBar().showMessage("正在扫描输入目录")

        self.scan_thread = QThread(self)
        self.scan_worker = ScanWorker(source_dir, self.ffmpeg_location.ffprobe_path)
        self.scan_worker.moveToThread(self.scan_thread)
        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.finished.connect(self._scan_finished)
        self.scan_worker.failed.connect(self._scan_failed)
        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.failed.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self.scan_worker.deleteLater)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)
        self.scan_thread.finished.connect(self._scan_thread_finished)
        self.scan_thread.start()

    @Slot(object)
    def _scan_finished(self, result: ScanResult) -> None:
        self._populate_videos(result.videos)
        self._populate_non_videos(result.non_videos)
        self.summary_label.setText(
            f"已扫描 {result.total_files} 个文件："
            f"{len(result.videos)} 个已确认视频，{len(result.non_videos)} 个其他或未确认文件。"
        )
        self.statusBar().showMessage("扫描完成")

    @Slot(str)
    def _scan_failed(self, message: str) -> None:
        self.summary_label.setText("扫描失败。")
        self.statusBar().showMessage("扫描失败")
        QMessageBox.critical(self, "扫描失败", message)

    @Slot()
    def _scan_thread_finished(self) -> None:
        self.scan_thread = None
        self.scan_worker = None
        self._set_scanning_enabled(True)

    def _set_scanning_enabled(self, enabled: bool) -> None:
        self.input_edit.setEnabled(enabled)
        self.browse_input_button.setEnabled(enabled)
        self.scan_button.setEnabled(enabled)
        self.ffmpeg_edit.setEnabled(enabled)
        self.browse_ffmpeg_button.setEnabled(enabled)
        self.refresh_ffmpeg_button.setEnabled(enabled)

    def _clear_tables(self) -> None:
        self.video_table.setRowCount(0)
        self.non_video_table.setRowCount(0)

    def _populate_videos(self, videos: list[VideoFile]) -> None:
        self.video_table.setRowCount(len(videos))
        for row, video in enumerate(videos):
            path = Path(video.path)
            values = [
                path.name,
                _format_duration(video.duration_seconds),
                _format_number(video.frame_rate),
                str(video.total_frames) if video.total_frames is not None else "未知",
                "有" if video.has_audio else "无",
                str(path),
            ]
            self._set_row(self.video_table, row, values)

    def _populate_non_videos(self, files: list[NonVideoFile]) -> None:
        self.non_video_table.setRowCount(len(files))
        for row, item in enumerate(files):
            path = Path(item.path)
            self._set_row(self.non_video_table, row, [path.name, item.reason, str(path)])

    def _set_row(self, table: QTableWidget, row: int, values: list[str]) -> None:
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, column, item)


def _format_duration(value: float | None) -> str:
    if value is None:
        return "未知"
    minutes, seconds = divmod(round(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def _format_number(value: float | None) -> str:
    if value is None:
        return "未知"
    return f"{value:.2f}".rstrip("0").rstrip(".")
