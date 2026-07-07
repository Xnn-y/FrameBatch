"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from framebatch.config.settings import SettingsStore
from framebatch.core.models import BlackFrameStatus, FrameTask, NonVideoFile, TaskStatus
from framebatch.core.naming import default_cover_output_dir, default_video_output_dir
from framebatch.core.scanner import ScanResult
from framebatch.core.tasks import create_frame_tasks, update_task_frame
from framebatch.ffmpeg.black_frame import BlackFrameCheckResult
from framebatch.ffmpeg.locator import FFmpegLocation, locate_ffmpeg
from framebatch.ui.workers import BlackFrameWorker, CoverWorker, ScanWorker


TASK_COLUMN_FILE = 0
TASK_COLUMN_FRAME = 1
TASK_COLUMN_BLACK = 2
TASK_COLUMN_STATUS = 3
TASK_COLUMN_DURATION = 4
TASK_COLUMN_FPS = 5
TASK_COLUMN_TOTAL_FRAMES = 6
TASK_COLUMN_AUDIO = 7
TASK_COLUMN_COVER = 8
TASK_COLUMN_REMOVED_VIDEO = 9
TASK_COLUMN_MESSAGE = 10

TAB_TASKS = 0
TAB_CANDIDATES = 1
TAB_NON_VIDEOS = 2

TASK_ROW_COLORS = {
    TaskStatus.SUCCESS: "#f0faf3",
    TaskStatus.FAILED: "#fff1f1",
    TaskStatus.WARNING: "#fff8e8",
    TaskStatus.RUNNING: "#edf6ff",
    TaskStatus.CANCELED: "#f1f4f8",
    TaskStatus.SKIPPED: "#f1f4f8",
}

TASK_STATUS_COLORS = {
    TaskStatus.PENDING: ("#edf1f7", "#44546a"),
    TaskStatus.SCANNING: ("#dcecff", "#184a86"),
    TaskStatus.READY: ("#e8f0fe", "#2451a6"),
    TaskStatus.WARNING: ("#fff0c2", "#7a4b00"),
    TaskStatus.RUNNING: ("#d9edff", "#0f5c99"),
    TaskStatus.SUCCESS: ("#d9f5df", "#176b35"),
    TaskStatus.FAILED: ("#ffe0e0", "#9f1d1d"),
    TaskStatus.CANCELED: ("#e6ebf2", "#4a5568"),
    TaskStatus.SKIPPED: ("#e6ebf2", "#4a5568"),
}

BLACK_STATUS_COLORS = {
    BlackFrameStatus.NOT_CHECKED: ("#edf1f7", "#44546a"),
    BlackFrameStatus.CHECKING: ("#d9edff", "#0f5c99"),
    BlackFrameStatus.OK: ("#d9f5df", "#176b35"),
    BlackFrameStatus.SUSPECTED_BLACK: ("#fff0c2", "#7a4b00"),
    BlackFrameStatus.FAILED: ("#ffe0e0", "#9f1d1d"),
}


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self.settings = settings
        self.ffmpeg_location: FFmpegLocation = locate_ffmpeg(
            configured_ffmpeg_path=self.settings.settings.ffmpeg_path
        )
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.black_thread: QThread | None = None
        self.black_worker: BlackFrameWorker | None = None
        self.cover_thread: QThread | None = None
        self.cover_worker: CoverWorker | None = None
        self.tasks: list[FrameTask] = []
        self.cover_completed_count = 0
        self.updating_task_table = False
        self.is_busy = False

        self.setWindowTitle("FrameBatch")
        self.resize(1280, 780)
        self.setStatusBar(QStatusBar(self))

        self.title_label = QLabel("FrameBatch")
        self.title_label.setObjectName("titleLabel")
        self.subtitle_label = QLabel("批量抽帧工作台")
        self.subtitle_label.setObjectName("subtitleLabel")

        self.input_edit = QLineEdit(self.settings.settings.last_input_dir or "")
        self.input_edit.setPlaceholderText("选择包含视频和其他文件的目录")
        self.browse_input_button = QPushButton("浏览")
        self.scan_button = QPushButton("扫描")

        self.cover_output_edit = QLineEdit(
            self.settings.settings.last_cover_output_dir
            or self.settings.settings.last_output_dir
            or ""
        )
        self.cover_output_edit.setPlaceholderText("默认在输入目录下创建 covers")
        self.browse_cover_output_button = QPushButton("浏览")
        self.default_cover_output_button = QPushButton("使用默认")

        self.video_output_edit = QLineEdit(
            self.settings.settings.last_video_output_dir
            or self.settings.settings.last_output_dir
            or ""
        )
        self.video_output_edit.setPlaceholderText("默认在输入目录下创建 videos")
        self.browse_video_output_button = QPushButton("浏览")
        self.default_video_output_button = QPushButton("使用默认")

        self.unified_name_edit = QLineEdit(self.settings.settings.unified_output_name or "")
        self.unified_name_edit.setPlaceholderText("留空使用原文件名；填写后按顺序自动编号")

        self.ffmpeg_edit = QLineEdit(self.settings.settings.ffmpeg_path or "")
        self.ffmpeg_edit.setPlaceholderText("可选：选择 ffmpeg.exe")
        self.browse_ffmpeg_button = QPushButton("浏览")
        self.refresh_ffmpeg_button = QPushButton("重新检测")
        self.ffmpeg_status_label = QLabel()

        self.default_frame_spin = QSpinBox()
        self.default_frame_spin.setRange(1, 999999999)
        self.default_frame_spin.setValue(max(1, self.settings.settings.default_frame))
        self.apply_frame_button = QPushButton("应用到全部")
        self.black_check_button = QPushButton("检测疑似黑屏")
        self.overwrite_check = QCheckBox("覆盖已存在封面")
        self.overwrite_check.setChecked(self.settings.settings.overwrite_outputs)
        self.extract_cover_button = QPushButton("开始抽帧")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.summary_label = QLabel("尚未扫描目录。")
        self.summary_label.setObjectName("summaryLabel")
        self.task_table = self._create_table(
            [
                "文件",
                "目标帧",
                "黑屏检测",
                "任务状态",
                "时长",
                "帧率",
                "总帧数",
                "音频",
                "封面输出",
                "去帧视频",
                "消息",
            ],
            editable=True,
        )
        self.candidate_table = self._create_table(["文件", "未确认原因"], editable=False)
        self.non_video_table = self._create_table(["文件", "原因"], editable=False)
        self.file_tabs = QTabWidget()
        self.file_tabs.setObjectName("fileTabs")
        self.file_tabs.addTab(self.task_table, "视频任务（0）")
        self.file_tabs.addTab(self.candidate_table, "候选视频 / 未确认（0）")
        self.file_tabs.addTab(self.non_video_table, "其他文件（0）")

        self._build_layout()
        self._connect_signals()
        self._apply_styles()
        self._refresh_ffmpeg_status(save=False)
        self._refresh_task_actions()

    def _build_layout(self) -> None:
        header = QWidget()
        header.setObjectName("headerBar")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(2)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.subtitle_label)

        input_group = QGroupBox("输入 / 输出")
        input_layout = QGridLayout(input_group)
        input_layout.addWidget(QLabel("输入目录"), 0, 0)
        input_layout.addWidget(self.input_edit, 0, 1)
        input_layout.addWidget(self.browse_input_button, 0, 2)
        input_layout.addWidget(self.scan_button, 0, 3)
        input_layout.addWidget(QLabel("封面目录"), 1, 0)
        input_layout.addWidget(self.cover_output_edit, 1, 1)
        input_layout.addWidget(self.browse_cover_output_button, 1, 2)
        input_layout.addWidget(self.default_cover_output_button, 1, 3)
        input_layout.addWidget(QLabel("视频目录"), 2, 0)
        input_layout.addWidget(self.video_output_edit, 2, 1)
        input_layout.addWidget(self.browse_video_output_button, 2, 2)
        input_layout.addWidget(self.default_video_output_button, 2, 3)
        input_layout.addWidget(QLabel("统一命名"), 3, 0)
        input_layout.addWidget(self.unified_name_edit, 3, 1, 1, 3)

        ffmpeg_group = QGroupBox("FFmpeg")
        ffmpeg_layout = QGridLayout(ffmpeg_group)
        ffmpeg_layout.addWidget(QLabel("ffmpeg.exe"), 0, 0)
        ffmpeg_layout.addWidget(self.ffmpeg_edit, 0, 1)
        ffmpeg_layout.addWidget(self.browse_ffmpeg_button, 0, 2)
        ffmpeg_layout.addWidget(self.refresh_ffmpeg_button, 0, 3)
        ffmpeg_layout.addWidget(self.ffmpeg_status_label, 1, 0, 1, 4)

        task_config_group = QGroupBox("任务配置")
        task_config_layout = QHBoxLayout(task_config_group)
        task_config_layout.addWidget(QLabel("默认目标帧"))
        task_config_layout.addWidget(self.default_frame_spin)
        task_config_layout.addWidget(self.apply_frame_button)
        task_config_layout.addWidget(self.black_check_button)
        task_config_layout.addWidget(self.overwrite_check)
        task_config_layout.addWidget(self.extract_cover_button)
        task_config_layout.addWidget(self.progress_bar)
        task_config_layout.addStretch(1)

        task_group = QGroupBox("文件列表")
        task_layout = QVBoxLayout(task_group)
        task_layout.addWidget(self.file_tabs)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)
        root_layout.addWidget(header)
        root_layout.addWidget(input_group)
        root_layout.addWidget(ffmpeg_group)
        root_layout.addWidget(task_config_group)
        root_layout.addWidget(self.summary_label)
        root_layout.addWidget(task_group, 1)

        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.browse_input_button.clicked.connect(self._choose_input_dir)
        self.browse_cover_output_button.clicked.connect(self._choose_cover_output_dir)
        self.default_cover_output_button.clicked.connect(self._use_default_cover_output_dir)
        self.browse_video_output_button.clicked.connect(self._choose_video_output_dir)
        self.default_video_output_button.clicked.connect(self._use_default_video_output_dir)
        self.browse_ffmpeg_button.clicked.connect(self._choose_ffmpeg)
        self.refresh_ffmpeg_button.clicked.connect(lambda: self._refresh_ffmpeg_status(save=True))
        self.scan_button.clicked.connect(self._start_scan)
        self.apply_frame_button.clicked.connect(self._apply_default_frame_to_all)
        self.black_check_button.clicked.connect(self._start_black_check)
        self.extract_cover_button.clicked.connect(self._start_cover_extract)
        self.overwrite_check.toggled.connect(self._overwrite_changed)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #e9eef5;
                color: #172033;
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            }
            QWidget#headerBar {
                background: #23354d;
                border: 1px solid #1d2b3e;
                border-radius: 8px;
            }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
                letter-spacing: 0px;
            }
            QLabel#subtitleLabel {
                color: #cbd6e5;
                font-size: 12px;
                font-weight: 400;
            }
            QGroupBox {
                font-weight: 600;
                color: #23354d;
                border: 1px solid #c8d2df;
                border-radius: 8px;
                margin-top: 12px;
                padding: 14px 12px 12px 12px;
                background: #fdfefe;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background: #fdfefe;
            }
            QLineEdit, QSpinBox {
                min-height: 30px;
                padding: 2px 9px;
                color: #172033;
                background: #ffffff;
                border: 1px solid #b8c4d4;
                border-radius: 6px;
                selection-background-color: #2f6fed;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #2f6fed;
                background: #fbfdff;
            }
            QCheckBox {
                color: #253852;
                font-weight: 600;
            }
            QTabWidget#fileTabs::pane {
                border: 1px solid #c8d2df;
                border-radius: 8px;
                background: #ffffff;
                top: -1px;
            }
            QTabWidget#fileTabs QTabBar::tab {
                min-height: 30px;
                padding: 6px 16px;
                margin-right: 4px;
                color: #23354d;
                background: #eef3f9;
                border: 1px solid #c8d2df;
                border-bottom: 0;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 700;
            }
            QTabWidget#fileTabs QTabBar::tab:hover {
                background: #f4f7fb;
            }
            QTabWidget#fileTabs QTabBar::tab:selected {
                color: #10213f;
                background: #ffffff;
                border-color: #9fb0c6;
            }
            QProgressBar {
                min-width: 150px;
                min-height: 24px;
                color: #172033;
                background: #e7edf5;
                border: 1px solid #c8d2df;
                border-radius: 6px;
                text-align: center;
                font-weight: 600;
            }
            QProgressBar::chunk {
                background: #2f6fed;
                border-radius: 5px;
            }
            QPushButton {
                min-height: 30px;
                padding: 4px 14px;
                color: #ffffff;
                background: #2f6fed;
                border: 1px solid #265dca;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3b7bf4;
            }
            QPushButton:pressed {
                background: #255fcf;
            }
            QPushButton:disabled {
                color: #8391a5;
                background: #e1e7ef;
                border: 1px solid #c9d3df;
            }
            QTableWidget {
                color: #172033;
                background: #ffffff;
                alternate-background-color: #f7f9fc;
                gridline-color: #dde5ef;
                border: 1px solid #c8d2df;
                border-radius: 6px;
                selection-background-color: #d7e5ff;
                selection-color: #10213f;
            }
            QHeaderView::section {
                color: #253852;
                background: #eef3f9;
                border: 0;
                border-right: 1px solid #d6dfeb;
                border-bottom: 1px solid #c8d2df;
                padding: 7px 8px;
                font-weight: 700;
            }
            QTableCornerButton::section {
                background: #eef3f9;
                border: 0;
                border-bottom: 1px solid #c8d2df;
                border-right: 1px solid #d6dfeb;
            }
            QScrollBar:vertical {
                background: #eef3f9;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #9fb0c6;
                border-radius: 6px;
                min-height: 32px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QStatusBar {
                color: #52637a;
                background: #e9eef5;
            }
            QLabel#summaryLabel {
                color: #2f4159;
                font-weight: 600;
                padding: 4px 2px;
            }
            QLabel#statusOk {
                color: #147240;
                font-weight: 600;
            }
            QLabel#statusError {
                color: #b42318;
                font-weight: 600;
            }
            """
        )

    def _create_table(self, headers: list[str], *, editable: bool) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        if editable:
            table.setEditTriggers(
                QTableWidget.EditTrigger.DoubleClicked
                | QTableWidget.EditTrigger.EditKeyPressed
                | QTableWidget.EditTrigger.SelectedClicked
            )
        else:
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
        if not self.cover_output_edit.text().strip():
            self.cover_output_edit.setText(str(default_cover_output_dir(Path(directory))))
        if not self.video_output_edit.text().strip():
            self.video_output_edit.setText(str(default_video_output_dir(Path(directory))))

    @Slot()
    def _choose_cover_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择封面输出目录",
            self.cover_output_edit.text(),
        )
        if not directory:
            return
        self.cover_output_edit.setText(directory)
        self.settings.update(last_cover_output_dir=directory)
        self.settings.save()

    @Slot()
    def _use_default_cover_output_dir(self) -> None:
        source_text = self.input_edit.text().strip()
        if not source_text:
            QMessageBox.information(self, "需要输入目录", "请先选择输入目录。")
            return
        self.cover_output_edit.setText(str(default_cover_output_dir(Path(source_text))))

    @Slot()
    def _choose_video_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择视频输出目录",
            self.video_output_edit.text(),
        )
        if not directory:
            return
        self.video_output_edit.setText(directory)
        self.settings.update(last_video_output_dir=directory)
        self.settings.save()

    @Slot()
    def _use_default_video_output_dir(self) -> None:
        source_text = self.input_edit.text().strip()
        if not source_text:
            QMessageBox.information(self, "需要输入目录", "请先选择输入目录。")
            return
        self.video_output_edit.setText(str(default_video_output_dir(Path(source_text))))

    @Slot(bool)
    def _overwrite_changed(self, checked: bool) -> None:
        self.settings.update(overwrite_outputs=checked)
        self.settings.save()

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
        self._refresh_task_actions()

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

        cover_output_dir = self._resolve_cover_output_dir()
        video_output_dir = self._resolve_video_output_dir()
        if cover_output_dir is None or video_output_dir is None:
            return
        self.cover_output_edit.setText(str(cover_output_dir))
        self.video_output_edit.setText(str(video_output_dir))
        self.settings.update(
            last_input_dir=str(source_dir),
            last_output_dir=str(cover_output_dir),
            last_cover_output_dir=str(cover_output_dir),
            last_video_output_dir=str(video_output_dir),
            unified_output_name=self.unified_name_edit.text().strip() or None,
            default_frame=self.default_frame_spin.value(),
            overwrite_outputs=self.overwrite_check.isChecked(),
        )
        self.settings.save()
        self.is_busy = True
        self._set_scanning_enabled(False)
        self._clear_tables()
        self.tasks = []
        self._refresh_task_actions()
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
        self.tasks = create_frame_tasks(result.videos, self.default_frame_spin.value())
        self._populate_tasks()
        self._populate_candidates(result.candidate_videos)
        self._populate_non_videos(result.non_videos)
        self.summary_label.setText(
            f"已扫描 {result.total_files} 个文件："
            f"{len(result.videos)} 个已确认视频，"
            f"{len(result.candidate_videos)} 个候选视频未确认，"
            f"{len(result.non_videos)} 个其他文件。"
        )
        self.statusBar().showMessage("扫描完成")
        self._refresh_task_actions()

    @Slot(str)
    def _scan_failed(self, message: str) -> None:
        self.summary_label.setText("扫描失败。")
        self.statusBar().showMessage("扫描失败")
        QMessageBox.critical(self, "扫描失败", message)

    @Slot()
    def _scan_thread_finished(self) -> None:
        self.scan_thread = None
        self.scan_worker = None
        self.is_busy = False
        self._set_scanning_enabled(True)

    @Slot()
    def _apply_default_frame_to_all(self) -> None:
        if not self.tasks:
            return
        frame = self.default_frame_spin.value()
        self.settings.update(default_frame=frame)
        self.settings.save()
        for task in self.tasks:
            update_task_frame(task, frame)
        self._populate_tasks()

    @Slot()
    def _start_black_check(self) -> None:
        if not self.tasks:
            QMessageBox.information(self, "没有任务", "请先扫描出有效视频任务。")
            return
        if not self.ffmpeg_location.ffmpeg_path:
            QMessageBox.warning(self, "FFmpeg 不可用", "请先配置 ffmpeg.exe，再检测疑似黑屏帧。")
            return

        for task in self.tasks:
            task.black_frame_status = BlackFrameStatus.CHECKING
            task.message = "正在检测目标帧..."
        self._populate_tasks()
        self.is_busy = True
        self._set_processing_enabled(False)
        self.statusBar().showMessage("正在检测疑似黑屏帧")

        self.black_thread = QThread(self)
        self.black_worker = BlackFrameWorker(self.tasks, self.ffmpeg_location.ffmpeg_path)
        self.black_worker.moveToThread(self.black_thread)
        self.black_thread.started.connect(self.black_worker.run)
        self.black_worker.task_checked.connect(self._black_task_checked)
        self.black_worker.failed.connect(self._black_check_failed)
        self.black_worker.finished.connect(self._black_check_finished)
        self.black_worker.failed.connect(self.black_thread.quit)
        self.black_worker.finished.connect(self.black_thread.quit)
        self.black_thread.finished.connect(self.black_worker.deleteLater)
        self.black_thread.finished.connect(self.black_thread.deleteLater)
        self.black_thread.finished.connect(self._black_thread_finished)
        self.black_thread.start()

    @Slot(int, object)
    def _black_task_checked(self, row: int, result: BlackFrameCheckResult) -> None:
        if row >= len(self.tasks):
            return
        task = self.tasks[row]
        task.black_frame_status = result.status
        task.message = result.message
        if result.status == BlackFrameStatus.SUSPECTED_BLACK:
            task.status = TaskStatus.WARNING
        elif result.status == BlackFrameStatus.OK:
            task.status = TaskStatus.READY
        else:
            task.status = TaskStatus.WARNING
        self._set_task_row(row, task)

    @Slot(str)
    def _black_check_failed(self, message: str) -> None:
        self.statusBar().showMessage("黑屏检测失败")
        QMessageBox.warning(self, "黑屏检测失败", message)

    @Slot()
    def _black_check_finished(self) -> None:
        self.statusBar().showMessage("黑屏检测完成")

    @Slot()
    def _black_thread_finished(self) -> None:
        self.black_thread = None
        self.black_worker = None
        self.is_busy = False
        self._set_processing_enabled(True)

    @Slot()
    def _start_cover_extract(self) -> None:
        if not self.tasks:
            QMessageBox.information(self, "没有任务", "请先扫描出有效视频任务。")
            return
        if not self.ffmpeg_location.ffmpeg_path:
            QMessageBox.warning(self, "FFmpeg 不可用", "请先配置 ffmpeg.exe，再开始抽帧。")
            return

        cover_output_dir = self._resolve_cover_output_dir()
        video_output_dir = self._resolve_video_output_dir()
        if cover_output_dir is None or video_output_dir is None:
            return

        self.settings.update(
            last_output_dir=str(cover_output_dir),
            last_cover_output_dir=str(cover_output_dir),
            last_video_output_dir=str(video_output_dir),
            unified_output_name=self.unified_name_edit.text().strip() or None,
            default_frame=self.default_frame_spin.value(),
            overwrite_outputs=self.overwrite_check.isChecked(),
        )
        self.settings.save()
        self.cover_output_edit.setText(str(cover_output_dir))
        self.video_output_edit.setText(str(video_output_dir))
        self.cover_completed_count = 0
        self.progress_bar.setValue(0)
        for task in self.tasks:
            task.status = TaskStatus.PENDING
            task.cover_path = None
            task.removed_video_path = None
            task.error_code = None
            task.message = "等待抽帧与生成去帧视频。"
        self._populate_tasks()

        self.is_busy = True
        self._set_processing_enabled(False)
        self.statusBar().showMessage("正在抽帧")

        self.cover_thread = QThread(self)
        self.cover_worker = CoverWorker(
            self.tasks,
            self.ffmpeg_location.ffmpeg_path,
            cover_output_dir,
            video_output_dir,
            unified_name=self.unified_name_edit.text().strip(),
            overwrite=self.overwrite_check.isChecked(),
        )
        self.cover_worker.moveToThread(self.cover_thread)
        self.cover_thread.started.connect(self.cover_worker.run)
        self.cover_worker.task_started.connect(self._cover_task_started)
        self.cover_worker.task_finished.connect(self._cover_task_finished)
        self.cover_worker.failed.connect(self._cover_extract_failed)
        self.cover_worker.finished.connect(self._cover_extract_finished)
        self.cover_worker.failed.connect(self.cover_thread.quit)
        self.cover_worker.finished.connect(self.cover_thread.quit)
        self.cover_thread.finished.connect(self.cover_worker.deleteLater)
        self.cover_thread.finished.connect(self.cover_thread.deleteLater)
        self.cover_thread.finished.connect(self._cover_thread_finished)
        self.cover_thread.start()

    def _resolve_cover_output_dir(self) -> Path | None:
        output_text = self.cover_output_edit.text().strip()
        if output_text:
            return Path(output_text)

        source_text = self.input_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, "需要封面目录", "请先选择输入目录或封面输出目录。")
            return None
        return default_cover_output_dir(Path(source_text))

    def _resolve_video_output_dir(self) -> Path | None:
        output_text = self.video_output_edit.text().strip()
        if output_text:
            return Path(output_text)

        source_text = self.input_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, "需要视频目录", "请先选择输入目录或视频输出目录。")
            return None
        return default_video_output_dir(Path(source_text))

    @Slot(int)
    def _cover_task_started(self, row: int) -> None:
        if row >= len(self.tasks):
            return
        task = self.tasks[row]
        task.status = TaskStatus.RUNNING
        task.message = "正在抽帧并生成去帧视频..."
        self._set_task_row(row, task)

    @Slot(int, bool, str, str, str, str)
    def _cover_task_finished(
        self,
        row: int,
        success: bool,
        cover_path: str,
        removed_video_path: str,
        error_code: str,
        message: str,
    ) -> None:
        if row >= len(self.tasks):
            return
        task = self.tasks[row]
        task.cover_path = cover_path or None
        task.removed_video_path = removed_video_path or None
        task.error_code = error_code or None
        task.message = message
        task.status = TaskStatus.SUCCESS if success else TaskStatus.FAILED
        self.cover_completed_count += 1
        self.progress_bar.setValue(round(self.cover_completed_count / len(self.tasks) * 100))
        self._set_task_row(row, task)

    @Slot(str)
    def _cover_extract_failed(self, message: str) -> None:
        self.statusBar().showMessage("抽帧失败")
        QMessageBox.warning(self, "抽帧失败", message)

    @Slot()
    def _cover_extract_finished(self) -> None:
        success_count = sum(1 for task in self.tasks if task.status == TaskStatus.SUCCESS)
        failed_count = sum(1 for task in self.tasks if task.status == TaskStatus.FAILED)
        cover_output_dir = self._resolve_cover_output_dir()
        video_output_dir = self._resolve_video_output_dir()
        output_text = (
            f"，封面目录：{cover_output_dir}，视频目录：{video_output_dir}"
            if cover_output_dir and video_output_dir
            else ""
        )
        self.summary_label.setText(
            f"处理完成：成功 {success_count} 个，失败 {failed_count} 个{output_text}。"
        )
        self.statusBar().showMessage("处理完成")

    @Slot()
    def _cover_thread_finished(self) -> None:
        self.cover_thread = None
        self.cover_worker = None
        self.is_busy = False
        self._set_processing_enabled(True)

    def _task_frame_changed(self, row: int, frame: int) -> None:
        if self.updating_task_table:
            return
        if row >= len(self.tasks):
            return

        try:
            update_task_frame(self.tasks[row], frame)
        except (TypeError, ValueError) as exc:
            self.tasks[row].status = TaskStatus.FAILED
            self.tasks[row].message = str(exc)
        self._set_task_row(row, self.tasks[row])

    def _set_scanning_enabled(self, enabled: bool) -> None:
        self.input_edit.setEnabled(enabled)
        self.browse_input_button.setEnabled(enabled)
        self.cover_output_edit.setEnabled(enabled)
        self.browse_cover_output_button.setEnabled(enabled)
        self.default_cover_output_button.setEnabled(enabled)
        self.video_output_edit.setEnabled(enabled)
        self.browse_video_output_button.setEnabled(enabled)
        self.default_video_output_button.setEnabled(enabled)
        self.unified_name_edit.setEnabled(enabled)
        self.scan_button.setEnabled(enabled)
        self.ffmpeg_edit.setEnabled(enabled)
        self.browse_ffmpeg_button.setEnabled(enabled)
        self.refresh_ffmpeg_button.setEnabled(enabled)
        self._refresh_task_actions()

    def _set_processing_enabled(self, enabled: bool) -> None:
        self.scan_button.setEnabled(enabled)
        self.input_edit.setEnabled(enabled)
        self.cover_output_edit.setEnabled(enabled)
        self.video_output_edit.setEnabled(enabled)
        self.browse_input_button.setEnabled(enabled)
        self.browse_cover_output_button.setEnabled(enabled)
        self.default_cover_output_button.setEnabled(enabled)
        self.browse_video_output_button.setEnabled(enabled)
        self.default_video_output_button.setEnabled(enabled)
        self.unified_name_edit.setEnabled(enabled)
        self.overwrite_check.setEnabled(enabled)
        self.task_table.setEnabled(enabled)
        self._refresh_task_actions()

    def _refresh_task_actions(self) -> None:
        has_tasks = bool(self.tasks)
        can_interact = has_tasks and not self.is_busy
        can_check_black = can_interact and self.ffmpeg_location.ffmpeg_path is not None
        can_extract_cover = can_interact and self.ffmpeg_location.ffmpeg_path is not None
        self.apply_frame_button.setEnabled(can_interact)
        self.black_check_button.setEnabled(can_check_black)
        self.extract_cover_button.setEnabled(can_extract_cover)
        if can_check_black:
            self.black_check_button.setToolTip("检测每个任务目标帧是否疑似黑屏")
        elif has_tasks and self.ffmpeg_location.ffmpeg_path is None:
            self.black_check_button.setToolTip("请先配置 ffmpeg.exe，再检测疑似黑屏")
        elif self.is_busy:
            self.black_check_button.setToolTip("当前任务运行中，请稍候")
        else:
            self.black_check_button.setToolTip("请先扫描出有效视频任务")

        if can_extract_cover:
            self.extract_cover_button.setToolTip("逐个任务抽取目标帧封面并生成去帧视频")
        elif has_tasks and self.ffmpeg_location.ffmpeg_path is None:
            self.extract_cover_button.setToolTip("请先配置 ffmpeg.exe，再开始抽帧")
        elif self.is_busy:
            self.extract_cover_button.setToolTip("当前任务运行中，请稍候")
        else:
            self.extract_cover_button.setToolTip("请先扫描出有效视频任务")

    def _clear_tables(self) -> None:
        self.task_table.setRowCount(0)
        self.candidate_table.setRowCount(0)
        self.non_video_table.setRowCount(0)
        self._refresh_file_tab_titles()
        self.file_tabs.setCurrentIndex(TAB_TASKS)

    def _populate_tasks(self) -> None:
        self.updating_task_table = True
        self.task_table.setRowCount(len(self.tasks))
        for row, task in enumerate(self.tasks):
            self._set_task_row(row, task)
        self.updating_task_table = False
        self._refresh_file_tab_titles()

    def _set_task_row(self, row: int, task: FrameTask) -> None:
        self.updating_task_table = True
        path = Path(task.video.path)
        values = [
            path.name,
            str(task.config.frame_user_index),
            _format_black_status(task.black_frame_status),
            _format_task_status(task.status),
            _format_duration(task.video.duration_seconds),
            _format_number(task.video.frame_rate),
            str(task.video.total_frames) if task.video.total_frames is not None else "未知",
            "有" if task.video.has_audio else "无",
            Path(task.cover_path).name if task.cover_path else "",
            Path(task.removed_video_path).name if task.removed_video_path else "",
            task.message,
        ]
        for column, value in enumerate(values):
            if column == TASK_COLUMN_FRAME:
                self._set_frame_spin(row, task)
            else:
                item = self._set_item(self.task_table, row, column, value, editable=False)
                self._style_task_item(item, column, task)
        self.updating_task_table = False

    def _set_frame_spin(self, row: int, task: FrameTask) -> None:
        spin = QSpinBox(self.task_table)
        current = task.config.frame_user_index
        total_frames = task.video.total_frames
        spin.setRange(1, max(current, total_frames or 999999999))
        spin.setValue(current)
        if total_frames is not None:
            spin.setToolTip(f"当前视频总帧数：{total_frames}")
        else:
            spin.setToolTip("当前视频总帧数未知")
        spin.valueChanged.connect(lambda value, row=row: self._task_frame_changed(row, value))
        self.task_table.setCellWidget(row, TASK_COLUMN_FRAME, spin)

    def _populate_candidates(self, files: list[NonVideoFile]) -> None:
        self.candidate_table.setRowCount(len(files))
        for row, item in enumerate(files):
            path = Path(item.path)
            self._set_item(self.candidate_table, row, 0, path.name, editable=False)
            self._set_item(self.candidate_table, row, 1, item.reason, editable=False)
        self._refresh_file_tab_titles()

    def _populate_non_videos(self, files: list[NonVideoFile]) -> None:
        self.non_video_table.setRowCount(len(files))
        for row, item in enumerate(files):
            path = Path(item.path)
            self._set_item(self.non_video_table, row, 0, path.name, editable=False)
            self._set_item(self.non_video_table, row, 1, item.reason, editable=False)
        self._refresh_file_tab_titles()

    def _refresh_file_tab_titles(self) -> None:
        self.file_tabs.setTabText(TAB_TASKS, f"视频任务（{self.task_table.rowCount()}）")
        self.file_tabs.setTabText(
            TAB_CANDIDATES,
            f"候选视频 / 未确认（{self.candidate_table.rowCount()}）",
        )
        self.file_tabs.setTabText(TAB_NON_VIDEOS, f"其他文件（{self.non_video_table.rowCount()}）")

    def _set_item(
        self,
        table: QTableWidget,
        row: int,
        column: int,
        value: str,
        *,
        editable: bool,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        if value:
            item.setToolTip(value)
        flags = item.flags()
        if editable:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, column, item)
        return item

    def _style_task_item(self, item: QTableWidgetItem, column: int, task: FrameTask) -> None:
        row_color = TASK_ROW_COLORS.get(task.status)
        if row_color:
            item.setBackground(QColor(row_color))

        if column in {
            TASK_COLUMN_BLACK,
            TASK_COLUMN_STATUS,
            TASK_COLUMN_DURATION,
            TASK_COLUMN_FPS,
            TASK_COLUMN_TOTAL_FRAMES,
            TASK_COLUMN_AUDIO,
        }:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if column == TASK_COLUMN_BLACK:
            background, foreground = BLACK_STATUS_COLORS[task.black_frame_status]
            item.setBackground(QColor(background))
            item.setForeground(QColor(foreground))
            return

        if column == TASK_COLUMN_STATUS:
            background, foreground = TASK_STATUS_COLORS[task.status]
            item.setBackground(QColor(background))
            item.setForeground(QColor(foreground))
            return

        if column == TASK_COLUMN_COVER and task.cover_path:
            item.setBackground(QColor("#e6f6ed"))
            item.setForeground(QColor("#176b35"))
            return

        if column == TASK_COLUMN_REMOVED_VIDEO and task.removed_video_path:
            item.setBackground(QColor("#e6f6ed"))
            item.setForeground(QColor("#176b35"))
            return

        if column == TASK_COLUMN_MESSAGE:
            if task.status == TaskStatus.FAILED:
                item.setForeground(QColor("#9f1d1d"))
            elif task.status == TaskStatus.WARNING:
                item.setForeground(QColor("#7a4b00"))


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


def _format_black_status(status: BlackFrameStatus) -> str:
    labels = {
        BlackFrameStatus.NOT_CHECKED: "未检测",
        BlackFrameStatus.CHECKING: "检测中",
        BlackFrameStatus.OK: "正常",
        BlackFrameStatus.SUSPECTED_BLACK: "疑似黑屏",
        BlackFrameStatus.FAILED: "检测失败",
    }
    return labels[status]


def _format_task_status(status: TaskStatus) -> str:
    labels = {
        TaskStatus.PENDING: "等待",
        TaskStatus.SCANNING: "扫描中",
        TaskStatus.READY: "就绪",
        TaskStatus.WARNING: "需确认",
        TaskStatus.RUNNING: "处理中",
        TaskStatus.SUCCESS: "成功",
        TaskStatus.FAILED: "失败",
        TaskStatus.CANCELED: "已取消",
        TaskStatus.SKIPPED: "已跳过",
    }
    return labels[status]
