"""Main application window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QSize, QThread, Qt, QUrl, Slot
from PySide6.QtGui import QColor, QDesktopServices
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
    QStatusBar,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from framebatch.config.settings import SettingsStore
from framebatch.core.models import FrameTask, NonVideoFile, TaskStatus
from framebatch.core.naming import default_video_output_dir
from framebatch.core.results import ResultPaths, write_result_files
from framebatch.core.results import application_dir, clear_history_runs, delete_history_run
from framebatch.core.results import latest_result_csv_path, load_history_runs, write_history_record_csv
from framebatch.core.scanner import ScanResult
from framebatch.core.tasks import create_frame_tasks
from framebatch.ffmpeg.cancel import CANCELED_ERROR_CODE
from framebatch.ffmpeg.locator import FFmpegLocation, locate_ffmpeg
from framebatch.ui.workers import CoverWorker, ScanWorker


TASK_COLUMN_FILE = 0
TASK_COLUMN_STATUS = 1
TASK_COLUMN_DURATION = 2
TASK_COLUMN_FPS = 3
TASK_COLUMN_TOTAL_FRAMES = 4
TASK_COLUMN_RESOLUTION = 5
TASK_COLUMN_AUDIO = 6
TASK_COLUMN_OUTPUT_VIDEO = 7
TASK_COLUMN_MESSAGE = 8

TAB_TASKS = 0
TAB_CANDIDATES = 1
TAB_NON_VIDEOS = 2
TAB_HISTORY = 3
HISTORY_COLUMN_ACTION = 8
IMAGE_FILTER = "图片文件 (*.jpg *.jpeg *.png *.webp *.bmp);;所有文件 (*)"

TASK_ROW_COLORS = {
    TaskStatus.SUCCESS: "#f0faf3",
    TaskStatus.FAILED: "#fff1f1",
    TaskStatus.RUNNING: "#edf6ff",
    TaskStatus.CANCELED: "#f1f4f8",
    TaskStatus.SKIPPED: "#f1f4f8",
}

TASK_STATUS_COLORS = {
    TaskStatus.PENDING: ("#edf1f7", "#44546a"),
    TaskStatus.READY: ("#e8f0fe", "#2451a6"),
    TaskStatus.RUNNING: ("#d9edff", "#0f5c99"),
    TaskStatus.SUCCESS: ("#d9f5df", "#176b35"),
    TaskStatus.FAILED: ("#ffe0e0", "#9f1d1d"),
    TaskStatus.CANCELED: ("#e6ebf2", "#4a5568"),
    TaskStatus.SKIPPED: ("#e6ebf2", "#4a5568"),
    TaskStatus.WARNING: ("#fff0c2", "#7a4b00"),
    TaskStatus.SCANNING: ("#dcecff", "#184a86"),
}


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self.settings = settings
        self.ffmpeg_location: FFmpegLocation = locate_ffmpeg(
            configured_ffmpeg_path=self.settings.settings.ffmpeg_path,
            app_root=application_dir(),
        )
        self.scan_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self.cover_thread: QThread | None = None
        self.cover_worker: CoverWorker | None = None
        self.tasks: list[FrameTask] = []
        self.scan_result: ScanResult | None = None
        self.history_records: list[dict[str, object]] = []
        self.completed_count = 0
        self.started_at: datetime | None = None
        self.is_busy = False
        self.is_processing = False
        self.cancel_requested = False

        self.setWindowTitle("FrameBatch")
        self.resize(1280, 780)
        self.setStatusBar(QStatusBar(self))

        self.title_label = QLabel("FrameBatch")
        self.title_label.setObjectName("titleLabel")
        self.subtitle_label = QLabel("批量为剧集视频插入统一封面帧")
        self.subtitle_label.setObjectName("subtitleLabel")

        self.input_edit = QLineEdit(self.settings.settings.last_input_dir or "")
        self.input_edit.setPlaceholderText("选择包含整部剧集视频的目录")
        self.browse_input_button = QPushButton("浏览")
        self.scan_button = QPushButton("扫描")

        self.cover_image_edit = QLineEdit(self.settings.settings.cover_image_path or "")
        self.cover_image_edit.setPlaceholderText("扫描后自动识别；识别不了可手动选择封面图片")
        self.browse_cover_image_button = QPushButton("浏览")
        self.clear_cover_image_button = QPushButton("清空")

        self.output_edit = QLineEdit(
            self.settings.settings.last_video_output_dir
            or self.settings.settings.last_output_dir
            or ""
        )
        self.output_edit.setPlaceholderText("默认在输入目录下创建 videos")
        self.browse_output_button = QPushButton("浏览")
        self.default_output_button = QPushButton("使用默认")

        self.unified_name_edit = QLineEdit(self.settings.settings.unified_output_name or "")
        self.unified_name_edit.setPlaceholderText("留空使用原文件名；填写后按 名称_1、名称_2 输出")

        self.ffmpeg_edit = QLineEdit(self.settings.settings.ffmpeg_path or "")
        self.ffmpeg_edit.setPlaceholderText("可选：选择 ffmpeg / ffmpeg.exe")
        self.browse_ffmpeg_button = QPushButton("浏览")
        self.refresh_ffmpeg_button = QPushButton("重新检测")
        self.ffmpeg_status_label = QLabel()

        self.overwrite_check = QCheckBox("覆盖已存在视频")
        self.overwrite_check.setChecked(self.settings.settings.overwrite_outputs)
        self.process_button = QPushButton("开始处理")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.summary_label = QLabel("尚未扫描目录。")
        self.summary_label.setObjectName("summaryLabel")

        self.task_table = self._create_table(
            ["文件", "任务状态", "时长", "帧率", "总帧数", "分辨率", "音频", "输出视频", "消息"]
        )
        self.candidate_table = self._create_table(["文件", "未确认原因"])
        self.non_video_table = self._create_table(["文件", "原因"])
        self.history_table = self._create_table(
            ["完成时间", "输入目录", "封面图片", "输出目录", "任务", "成功", "失败", "取消", "操作"]
        )
        self.history_table.horizontalHeader().setStretchLastSection(False)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(
            HISTORY_COLUMN_ACTION,
            QHeaderView.ResizeMode.Fixed,
        )
        self.history_table.setColumnWidth(HISTORY_COLUMN_ACTION, 58)

        self.refresh_history_button = QPushButton("刷新历史")
        self.open_output_dir_button = QPushButton("打开输出目录")
        self.clear_history_button = QPushButton("清空历史")
        self.clear_history_button.setObjectName("clearHistoryButton")
        self.clear_history_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))

        self.file_tabs = QTabWidget()
        self.file_tabs.setObjectName("fileTabs")
        self.file_tabs.addTab(self.task_table, "视频任务（0）")
        self.file_tabs.addTab(self.candidate_table, "候选视频 / 未确认（0）")
        self.file_tabs.addTab(self.non_video_table, "其他文件（0）")
        self.file_tabs.addTab(self.history_table, "历史记录（0）")

        self._build_layout()
        self._connect_signals()
        self._apply_styles()
        self._refresh_ffmpeg_status(save=False)
        self._refresh_history()
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
        input_layout.addWidget(QLabel("封面图片"), 1, 0)
        input_layout.addWidget(self.cover_image_edit, 1, 1)
        input_layout.addWidget(self.browse_cover_image_button, 1, 2)
        input_layout.addWidget(self.clear_cover_image_button, 1, 3)
        input_layout.addWidget(QLabel("输出目录"), 2, 0)
        input_layout.addWidget(self.output_edit, 2, 1)
        input_layout.addWidget(self.browse_output_button, 2, 2)
        input_layout.addWidget(self.default_output_button, 2, 3)
        input_layout.addWidget(QLabel("统一命名"), 3, 0)
        input_layout.addWidget(self.unified_name_edit, 3, 1, 1, 3)

        ffmpeg_group = QGroupBox("FFmpeg")
        ffmpeg_layout = QGridLayout(ffmpeg_group)
        ffmpeg_layout.addWidget(QLabel("ffmpeg"), 0, 0)
        ffmpeg_layout.addWidget(self.ffmpeg_edit, 0, 1)
        ffmpeg_layout.addWidget(self.browse_ffmpeg_button, 0, 2)
        ffmpeg_layout.addWidget(self.refresh_ffmpeg_button, 0, 3)
        ffmpeg_layout.addWidget(self.ffmpeg_status_label, 1, 0, 1, 4)

        task_config_group = QGroupBox("任务配置")
        task_config_layout = QHBoxLayout(task_config_group)
        task_config_layout.addWidget(self.overwrite_check)
        task_config_layout.addWidget(self.process_button)
        task_config_layout.addWidget(self.progress_bar)
        task_config_layout.addStretch(1)

        task_group = QGroupBox("文件列表")
        task_layout = QVBoxLayout(task_group)
        history_action_layout = QHBoxLayout()
        history_action_layout.addWidget(self.refresh_history_button)
        history_action_layout.addWidget(self.open_output_dir_button)
        history_action_layout.addStretch(1)
        history_action_layout.addWidget(self.clear_history_button)
        task_layout.addLayout(history_action_layout)
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
        self.browse_cover_image_button.clicked.connect(self._choose_cover_image)
        self.clear_cover_image_button.clicked.connect(self._clear_cover_image)
        self.browse_output_button.clicked.connect(self._choose_output_dir)
        self.default_output_button.clicked.connect(self._use_default_output_dir)
        self.browse_ffmpeg_button.clicked.connect(self._choose_ffmpeg)
        self.refresh_ffmpeg_button.clicked.connect(lambda: self._refresh_ffmpeg_status(save=True))
        self.scan_button.clicked.connect(self._start_scan)
        self.process_button.clicked.connect(self._process_button_clicked)
        self.overwrite_check.toggled.connect(self._overwrite_changed)
        self.cover_image_edit.textChanged.connect(lambda _text: self._refresh_task_actions())
        self.refresh_history_button.clicked.connect(self._refresh_history)
        self.open_output_dir_button.clicked.connect(self._open_output_dir)
        self.clear_history_button.clicked.connect(self._clear_history)
        self.output_edit.textChanged.connect(lambda _text: self._refresh_history_actions())
        self.history_table.itemSelectionChanged.connect(self._refresh_history_actions)
        self.history_table.cellDoubleClicked.connect(self._open_history_csv_at_row)
        self.file_tabs.currentChanged.connect(lambda _index: self._refresh_history_actions())

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #e9eef5; color: #172033; font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; }
            QWidget#headerBar { background: #23354d; border: 1px solid #1d2b3e; border-radius: 8px; }
            QLabel#titleLabel { color: #ffffff; font-size: 22px; font-weight: 700; letter-spacing: 0px; }
            QLabel#subtitleLabel { color: #cbd6e5; font-size: 12px; font-weight: 400; }
            QGroupBox { font-weight: 600; color: #23354d; border: 1px solid #c8d2df; border-radius: 8px; margin-top: 12px; padding: 14px 12px 12px 12px; background: #fdfefe; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; background: #fdfefe; }
            QLineEdit { min-height: 30px; padding: 2px 9px; color: #172033; background: #ffffff; border: 1px solid #b8c4d4; border-radius: 6px; selection-background-color: #2f6fed; }
            QLineEdit:focus { border: 1px solid #2f6fed; background: #fbfdff; }
            QCheckBox { color: #253852; font-weight: 600; }
            QProgressBar { min-width: 150px; min-height: 24px; color: #172033; background: #e7edf5; border: 1px solid #c8d2df; border-radius: 6px; text-align: center; font-weight: 600; }
            QProgressBar::chunk { background: #2f6fed; border-radius: 5px; }
            QPushButton { min-height: 30px; padding: 4px 14px; color: #ffffff; background: #2f6fed; border: 1px solid #265dca; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background: #3b7bf4; }
            QPushButton:pressed { background: #255fcf; }
            QPushButton:disabled { color: #8391a5; background: #e1e7ef; border: 1px solid #c9d3df; }
            QPushButton#clearHistoryButton { color: #9f1d1d; background: #fff5f5; border-color: #f5b5b5; }
            QPushButton#clearHistoryButton:hover { color: #ffffff; background: #d92d20; border-color: #b42318; }
            QPushButton#clearHistoryButton:disabled { color: #b7a0a0; background: #f1e8e8; border-color: #dfcaca; }
            QToolButton#historyDeleteButton { min-width: 28px; min-height: 28px; background: transparent; border: 1px solid transparent; border-radius: 6px; }
            QToolButton#historyDeleteButton:hover { background: #fee2e2; border-color: #fca5a5; }
            QTableWidget { color: #172033; background: #ffffff; alternate-background-color: #f7f9fc; gridline-color: #dde5ef; border: 1px solid #c8d2df; border-radius: 6px; selection-background-color: #d7e5ff; selection-color: #10213f; }
            QHeaderView::section { color: #253852; background: #eef3f9; border: 0; border-right: 1px solid #d6dfeb; border-bottom: 1px solid #c8d2df; padding: 7px 8px; font-weight: 700; }
            QTabWidget#fileTabs::pane { border: 1px solid #c8d2df; border-radius: 8px; background: #ffffff; top: -1px; }
            QTabWidget#fileTabs QTabBar::tab { min-height: 30px; padding: 6px 16px; margin-right: 4px; color: #23354d; background: #eef3f9; border: 1px solid #c8d2df; border-bottom: 0; border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 700; }
            QTabWidget#fileTabs QTabBar::tab:selected { color: #10213f; background: #ffffff; border-color: #9fb0c6; }
            QLabel#summaryLabel { color: #2f4159; font-weight: 600; padding: 4px 2px; }
            QLabel#statusOk { color: #147240; font-weight: 600; }
            QLabel#statusError { color: #b42318; font-weight: 600; }
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
        if not self.output_edit.text().strip():
            self.output_edit.setText(str(default_video_output_dir(Path(directory))))

    @Slot()
    def _choose_cover_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择封面图片",
            self.cover_image_edit.text(),
            IMAGE_FILTER,
        )
        if not path:
            return
        self.cover_image_edit.setText(path)
        self.settings.update(cover_image_path=path)
        self.settings.save()
        self._refresh_task_actions()

    @Slot()
    def _clear_cover_image(self) -> None:
        self.cover_image_edit.clear()
        self.settings.update(cover_image_path=None)
        self.settings.save()
        self._refresh_task_actions()

    @Slot()
    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出视频目录", self.output_edit.text())
        if not directory:
            return
        self.output_edit.setText(directory)
        self.settings.update(last_output_dir=directory, last_video_output_dir=directory)
        self.settings.save()

    @Slot()
    def _use_default_output_dir(self) -> None:
        source_text = self.input_edit.text().strip()
        if not source_text:
            QMessageBox.information(self, "需要输入目录", "请先选择输入目录。")
            return
        self.output_edit.setText(str(default_video_output_dir(Path(source_text))))

    @Slot(bool)
    def _overwrite_changed(self, checked: bool) -> None:
        self.settings.update(overwrite_outputs=checked)
        self.settings.save()

    @Slot()
    def _choose_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 ffmpeg",
            self.ffmpeg_edit.text(),
            "FFmpeg 可执行文件 (ffmpeg ffmpeg.exe);;所有文件 (*)",
        )
        if not path:
            return
        self.ffmpeg_edit.setText(path)
        self.settings.update(ffmpeg_path=path)
        self.settings.save()
        self._refresh_ffmpeg_status(save=True)

    def _refresh_ffmpeg_status(self, *, save: bool) -> None:
        configured_path = self.ffmpeg_edit.text().strip() or None
        self.ffmpeg_location = locate_ffmpeg(
            configured_ffmpeg_path=configured_path,
            app_root=application_dir(),
        )
        if save:
            self.settings.update(
                ffmpeg_path=str(self.ffmpeg_location.ffmpeg_path) if self.ffmpeg_location.ffmpeg_path else configured_path,
                ffprobe_path=str(self.ffmpeg_location.ffprobe_path) if self.ffmpeg_location.ffprobe_path else None,
            )
            self.settings.save()
        self.ffmpeg_status_label.setObjectName("statusOk" if self.ffmpeg_location.is_available else "statusError")
        self.ffmpeg_status_label.setText(self.ffmpeg_location.message)
        self.ffmpeg_status_label.style().unpolish(self.ffmpeg_status_label)
        self.ffmpeg_status_label.style().polish(self.ffmpeg_status_label)
        self._refresh_task_actions()

    @Slot()
    def _start_scan(self) -> None:
        source_dir = Path(self.input_edit.text().strip())
        if not source_dir.is_dir():
            QMessageBox.warning(self, "目录不存在", f"输入目录不存在：\n{source_dir}")
            return
        output_dir = self._resolve_output_dir()
        if output_dir is None:
            return
        self.output_edit.setText(str(output_dir))
        self.settings.update(
            last_input_dir=str(source_dir),
            last_output_dir=str(output_dir),
            last_video_output_dir=str(output_dir),
            cover_image_path=self.cover_image_edit.text().strip() or None,
            unified_output_name=self.unified_name_edit.text().strip() or None,
            overwrite_outputs=self.overwrite_check.isChecked(),
        )
        self.settings.save()
        self.is_busy = True
        self._set_inputs_enabled(False)
        self._clear_tables()
        self.tasks = []
        self.scan_result = None
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
        self.scan_result = result
        self._refresh_detected_cover_image()
        self.tasks = create_frame_tasks(result.videos, 1)
        self._populate_tasks()
        self._populate_candidates(result.candidate_videos)
        self._populate_non_videos(result.non_videos)
        cover_text = self._cover_summary_text()
        self.summary_label.setText(
            f"已扫描 {result.total_files} 个文件：{len(result.videos)} 个已确认视频，"
            f"{len(result.cover_images)} 张封面候选，{len(result.candidate_videos)} 个候选视频未确认，"
            f"{len(result.non_videos)} 个其他文件。{cover_text}"
        )
        self.statusBar().showMessage("扫描完成")
        self._refresh_task_actions()

    @Slot(str)
    def _scan_failed(self, message: str) -> None:
        self.summary_label.setText("扫描失败。")
        self.statusBar().showMessage("扫描失败")
        self.cover_image_edit.clear()
        QMessageBox.critical(self, "扫描失败", message)

    @Slot()
    def _scan_thread_finished(self) -> None:
        self.scan_thread = None
        self.scan_worker = None
        self.is_busy = False
        self._set_inputs_enabled(True)

    def _process_button_clicked(self) -> None:
        if self.is_processing:
            self._request_cancel()
            return
        self._start_processing()

    def _request_cancel(self) -> None:
        if not self.cover_worker or self.cancel_requested:
            return
        self.cancel_requested = True
        self.process_button.setText("正在终止...")
        self.process_button.setEnabled(False)
        self.statusBar().showMessage("正在终止处理")
        self.cover_worker.cancel()

    def _start_processing(self) -> None:
        if not self.tasks:
            QMessageBox.information(self, "没有任务", "请先扫描出有效视频任务。")
            return
        if not self.ffmpeg_location.ffmpeg_path:
            QMessageBox.warning(self, "FFmpeg 不可用", "请先配置 ffmpeg，再开始处理。")
            return
        cover_image_path = self._selected_cover_image_path()
        if cover_image_path is None:
            QMessageBox.warning(self, "封面图片不存在", "请先扫描自动识别封面，或手动选择一张有效封面图片。")
            return
        if not cover_image_path.is_file():
            QMessageBox.warning(self, "封面图片不存在", f"当前封面图片不存在：\n{cover_image_path}")
            return
        output_dir = self._resolve_output_dir()
        if output_dir is None:
            return

        self.settings.update(
            last_output_dir=str(output_dir),
            last_video_output_dir=str(output_dir),
            cover_image_path=str(cover_image_path),
            unified_output_name=self.unified_name_edit.text().strip() or None,
            overwrite_outputs=self.overwrite_check.isChecked(),
        )
        self.settings.save()
        self.output_edit.setText(str(output_dir))
        self.completed_count = 0
        self.started_at = datetime.now().astimezone()
        self.progress_bar.setValue(0)
        for task in self.tasks:
            task.status = TaskStatus.PENDING
            task.cover_path = str(cover_image_path)
            task.removed_video_path = None
            task.error_code = None
            task.message = "等待插入封面帧。"
        self._populate_tasks()

        self.is_busy = True
        self.is_processing = True
        self.cancel_requested = False
        self._set_processing_enabled(False)
        self.statusBar().showMessage("正在处理视频")

        self.cover_thread = QThread(self)
        self.cover_worker = CoverWorker(
            self.tasks,
            self.ffmpeg_location.ffmpeg_path,
            cover_image_path,
            output_dir,
            unified_name=self.unified_name_edit.text().strip(),
            overwrite=self.overwrite_check.isChecked(),
        )
        self.cover_worker.moveToThread(self.cover_thread)
        self.cover_thread.started.connect(self.cover_worker.run)
        self.cover_worker.task_started.connect(self._task_started)
        self.cover_worker.task_finished.connect(self._task_finished)
        self.cover_worker.failed.connect(self._processing_failed)
        self.cover_worker.finished.connect(self._processing_finished)
        self.cover_worker.failed.connect(self.cover_thread.quit)
        self.cover_worker.finished.connect(self.cover_thread.quit)
        self.cover_thread.finished.connect(self.cover_worker.deleteLater)
        self.cover_thread.finished.connect(self.cover_thread.deleteLater)
        self.cover_thread.finished.connect(self._processing_thread_finished)
        self.cover_thread.start()

    def _resolve_output_dir(self) -> Path | None:
        output_text = self.output_edit.text().strip()
        if output_text:
            return Path(output_text)
        source_text = self.input_edit.text().strip()
        if not source_text:
            QMessageBox.warning(self, "需要输出目录", "请先选择输入目录或输出视频目录。")
            return None
        return default_video_output_dir(Path(source_text))

    @Slot(int)
    def _task_started(self, row: int) -> None:
        if row >= len(self.tasks):
            return
        task = self.tasks[row]
        task.status = TaskStatus.RUNNING
        task.message = "正在插入封面帧..."
        self._set_task_row(row, task)

    @Slot(int, bool, str, str, str, str)
    def _task_finished(
        self,
        row: int,
        success: bool,
        cover_path: str,
        output_video_path: str,
        error_code: str,
        message: str,
    ) -> None:
        if row >= len(self.tasks):
            return
        task = self.tasks[row]
        task.cover_path = cover_path or task.cover_path
        task.removed_video_path = output_video_path or None
        task.error_code = error_code or None
        task.message = message
        if success:
            task.status = TaskStatus.SUCCESS
        elif error_code == CANCELED_ERROR_CODE:
            task.status = TaskStatus.CANCELED
        elif error_code == "TASK_SKIPPED":
            task.status = TaskStatus.SKIPPED
        else:
            task.status = TaskStatus.FAILED
        self.completed_count += 1
        self.progress_bar.setValue(round(self.completed_count / len(self.tasks) * 100))
        self._set_task_row(row, task)

    @Slot(str)
    def _processing_failed(self, message: str) -> None:
        self.statusBar().showMessage("处理失败")
        QMessageBox.warning(self, "处理失败", message)

    @Slot()
    def _processing_finished(self) -> None:
        success_count = sum(1 for task in self.tasks if task.status == TaskStatus.SUCCESS)
        failed_count = sum(1 for task in self.tasks if task.status == TaskStatus.FAILED)
        canceled_count = sum(1 for task in self.tasks if task.status == TaskStatus.CANCELED)
        skipped_count = sum(1 for task in self.tasks if task.status == TaskStatus.SKIPPED)
        output_dir = self._resolve_output_dir()
        result_paths: ResultPaths | None = None
        if output_dir:
            result_paths = self._write_result_report(Path(self.cover_image_edit.text().strip()), output_dir)
        output_text = f"，输出目录：{output_dir}" if output_dir else ""
        if result_paths is not None:
            self._refresh_history()
            output_text += f"，结果：{result_paths.result_csv.name}"
        if canceled_count or skipped_count or self.cancel_requested:
            self.summary_label.setText(
                f"已终止：成功 {success_count} 个，失败 {failed_count} 个，"
                f"取消 {canceled_count} 个，跳过 {skipped_count} 个{output_text}。"
            )
            self.statusBar().showMessage("处理已终止")
        else:
            self.summary_label.setText(f"处理完成：成功 {success_count} 个，失败 {failed_count} 个{output_text}。")
            self.statusBar().showMessage("处理完成")

    def _write_result_report(self, cover_image_path: Path, output_dir: Path) -> ResultPaths | None:
        started_at = self.started_at or datetime.now().astimezone()
        finished_at = datetime.now().astimezone()
        scan_result = self.scan_result
        source_dir = scan_result.source_dir if scan_result is not None else Path(self.input_edit.text().strip())
        candidate_videos = scan_result.candidate_videos if scan_result is not None else []
        non_videos = scan_result.non_videos if scan_result is not None else []
        try:
            return write_result_files(
                source_dir=source_dir,
                cover_image_path=cover_image_path,
                output_dir=output_dir,
                history_dir=self.settings.path.parent,
                started_at=started_at,
                finished_at=finished_at,
                tasks=self.tasks,
                candidate_videos=candidate_videos,
                non_videos=non_videos,
            )
        except Exception as exc:
            QMessageBox.warning(self, "结果写入失败", f"处理已完成，但结果文件写入失败：\n{exc}")
            return None

    @Slot()
    def _processing_thread_finished(self) -> None:
        self.cover_thread = None
        self.cover_worker = None
        self.is_busy = False
        self.started_at = None
        self.is_processing = False
        self.cancel_requested = False
        self._set_processing_enabled(True)

    def _refresh_detected_cover_image(self) -> None:
        cover_path = self._detected_cover_image_path()
        if cover_path is not None:
            self.cover_image_edit.setText(str(cover_path))

    def _detected_cover_image_path(self) -> Path | None:
        if self.scan_result is None or len(self.scan_result.cover_images) != 1:
            return None
        return Path(self.scan_result.cover_images[0].path)

    def _selected_cover_image_path(self) -> Path | None:
        cover_text = self.cover_image_edit.text().strip()
        return Path(cover_text) if cover_text else None

    def _cover_summary_text(self) -> str:
        if self.scan_result is None:
            return ""
        count = len(self.scan_result.cover_images)
        if count == 1:
            return f"已自动识别封面：{Path(self.scan_result.cover_images[0].path).name}。"
        if count == 0:
            return "未检测到封面图片，请在输入目录中放入一张图片后重新扫描。"
        return f"检测到 {count} 张图片，未自动选择封面；可手动选择其中一张。"

    def _cover_blocking_message(self) -> str:
        if self.scan_result is None:
            return "请先扫描输入目录，程序会自动识别目录中的唯一图片作为封面。"
        count = len(self.scan_result.cover_images)
        if count == 0:
            return "输入目录中没有检测到封面图片，请放入一张 jpg、png、webp 或 bmp 图片后重新扫描。"
        return f"输入目录中检测到 {count} 张图片，无法判断哪一张是统一封面。请手动选择一张封面图片。"

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self.input_edit.setEnabled(enabled)
        self.browse_input_button.setEnabled(enabled)
        self.cover_image_edit.setEnabled(enabled)
        self.browse_cover_image_button.setEnabled(enabled)
        self.clear_cover_image_button.setEnabled(enabled)
        self.output_edit.setEnabled(enabled)
        self.browse_output_button.setEnabled(enabled)
        self.default_output_button.setEnabled(enabled)
        self.unified_name_edit.setEnabled(enabled)
        self.scan_button.setEnabled(enabled)
        self.ffmpeg_edit.setEnabled(enabled)
        self.browse_ffmpeg_button.setEnabled(enabled)
        self.refresh_ffmpeg_button.setEnabled(enabled)
        self._refresh_task_actions()

    def _set_processing_enabled(self, enabled: bool) -> None:
        self.scan_button.setEnabled(enabled)
        self.input_edit.setEnabled(enabled)
        self.cover_image_edit.setEnabled(enabled)
        self.output_edit.setEnabled(enabled)
        self.browse_input_button.setEnabled(enabled)
        self.browse_cover_image_button.setEnabled(enabled)
        self.clear_cover_image_button.setEnabled(enabled)
        self.browse_output_button.setEnabled(enabled)
        self.default_output_button.setEnabled(enabled)
        self.unified_name_edit.setEnabled(enabled)
        self.overwrite_check.setEnabled(enabled)
        self.task_table.setEnabled(True)
        self._refresh_task_actions()

    def _refresh_task_actions(self) -> None:
        has_tasks = bool(self.tasks)
        has_cover = self._selected_cover_image_path() is not None
        can_process = has_tasks and has_cover and not self.is_busy and self.ffmpeg_location.ffmpeg_path is not None
        if self.is_processing:
            self.process_button.setText("正在终止..." if self.cancel_requested else "终止处理")
            self.process_button.setEnabled(not self.cancel_requested)
        else:
            self.process_button.setText("开始处理")
            self.process_button.setEnabled(can_process)
        if can_process:
            self.process_button.setToolTip("为每个视频开头插入同一张封面图片，并输出新的 MP4")
        elif has_tasks and self.ffmpeg_location.ffmpeg_path is None:
            self.process_button.setToolTip("请先配置 ffmpeg，再开始处理")
        elif has_tasks and not has_cover:
            self.process_button.setToolTip("请先扫描自动识别封面，或手动选择一张封面图片。")
        elif self.is_busy:
            self.process_button.setToolTip("当前任务运行中，请稍等")
        else:
            self.process_button.setToolTip("请先扫描出有效视频任务")

    def _clear_tables(self) -> None:
        self.task_table.setRowCount(0)
        self.candidate_table.setRowCount(0)
        self.non_video_table.setRowCount(0)
        self.cover_image_edit.clear()
        self._refresh_file_tab_titles()
        self.file_tabs.setCurrentIndex(TAB_TASKS)

    def _populate_tasks(self) -> None:
        self.task_table.setRowCount(len(self.tasks))
        for row, task in enumerate(self.tasks):
            self._set_task_row(row, task)
        self._refresh_file_tab_titles()

    def _set_task_row(self, row: int, task: FrameTask) -> None:
        path = Path(task.video.path)
        values = [
            path.name,
            _format_task_status(task.status),
            _format_duration(task.video.duration_seconds),
            _format_number(task.video.frame_rate),
            str(task.video.total_frames) if task.video.total_frames is not None else "未知",
            _format_resolution(task.video.width, task.video.height),
            "有" if task.video.has_audio else "无",
            Path(task.removed_video_path).name if task.removed_video_path else "",
            task.message,
        ]
        for column, value in enumerate(values):
            item = self._set_item(self.task_table, row, column, value)
            self._style_task_item(item, column, task)

    def _populate_candidates(self, files: list[NonVideoFile]) -> None:
        self.candidate_table.setRowCount(len(files))
        for row, item in enumerate(files):
            path = Path(item.path)
            self._set_item(self.candidate_table, row, 0, path.name)
            self._set_item(self.candidate_table, row, 1, item.reason)
        self._refresh_file_tab_titles()

    def _populate_non_videos(self, files: list[NonVideoFile]) -> None:
        self.non_video_table.setRowCount(len(files))
        for row, item in enumerate(files):
            path = Path(item.path)
            self._set_item(self.non_video_table, row, 0, path.name)
            self._set_item(self.non_video_table, row, 1, item.reason)
        self._refresh_file_tab_titles()

    def _refresh_file_tab_titles(self) -> None:
        self.file_tabs.setTabText(TAB_TASKS, f"视频任务（{self.task_table.rowCount()}）")
        self.file_tabs.setTabText(TAB_CANDIDATES, f"候选视频 / 未确认（{self.candidate_table.rowCount()}）")
        self.file_tabs.setTabText(TAB_NON_VIDEOS, f"其他文件（{self.non_video_table.rowCount()}）")
        self.file_tabs.setTabText(TAB_HISTORY, f"历史记录（{self.history_table.rowCount()}）")

    def _refresh_history(self) -> None:
        self.history_records = load_history_runs(self.settings.path.parent)
        self.history_table.setRowCount(len(self.history_records))
        for row, record in enumerate(self.history_records):
            values = [
                _format_history_time(_record_text(record, "finished_at")),
                _record_text(record, "source_dir"),
                _record_text(record, "cover_image_path") or _record_text(record, "cover_output_dir"),
                _record_text(record, "output_dir") or _record_text(record, "video_output_dir"),
                _record_text(record, "task_count"),
                _record_text(record, "success_count"),
                _record_text(record, "failed_count"),
                _record_text(record, "canceled_count"),
            ]
            for column, value in enumerate(values):
                item = self._set_item(self.history_table, row, column, value)
                if column in {4, 5, 6, 7}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._set_history_delete_button(row, record)
        self._refresh_file_tab_titles()
        self._refresh_history_actions()

    def _refresh_history_actions(self) -> None:
        self.refresh_history_button.setEnabled(True)
        self.clear_history_button.setEnabled(bool(self.history_records))
        self.open_output_dir_button.setEnabled(bool(self.output_edit.text().strip()))

    def _selected_history_record(self) -> dict[str, object] | None:
        row = self.history_table.currentRow()
        if row < 0 or row >= len(self.history_records):
            return None
        return self.history_records[row]

    def _set_history_delete_button(self, row: int, record: dict[str, object]) -> None:
        button = QToolButton()
        button.setObjectName("historyDeleteButton")
        button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        button.setIconSize(QSize(16, 16))
        button.setToolTip("删除这条历史记录")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, run_id=_record_text(record, "run_id"): self._delete_history_run(run_id))

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(button)
        layout.addStretch(1)
        self.history_table.setCellWidget(row, HISTORY_COLUMN_ACTION, container)

    def _delete_history_run(self, run_id: str) -> None:
        if not run_id:
            return
        response = QMessageBox.question(
            self,
            "删除历史记录",
            "确定删除这条历史记录吗？\n不会删除已生成的视频。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        if delete_history_run(self.settings.path.parent, run_id):
            self.statusBar().showMessage("已删除历史记录")
        else:
            QMessageBox.warning(self, "删除失败", "没有找到这条历史记录，可能已经被删除。")
        self._refresh_history()

    @Slot()
    def _clear_history(self) -> None:
        if not self.history_records:
            return
        response = QMessageBox.question(
            self,
            "清空历史记录",
            "确定清空全部历史记录吗？\n不会删除已生成的视频。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        removed_count = clear_history_runs(self.settings.path.parent)
        self.statusBar().showMessage(f"已清空历史记录（{removed_count} 条）")
        self._refresh_history()

    @Slot()
    def _open_output_dir(self) -> None:
        path_text = self.output_edit.text().strip()
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists():
            QMessageBox.information(self, "输出目录未创建", f"输出目录还未创建：\n{path}")
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not opened:
            QMessageBox.warning(self, "无法打开输出目录", f"无法打开输出目录：\n{path}")

    def _open_selected_history_path(self, key: str, label: str) -> None:
        record = self._selected_history_record()
        if record is None:
            return
        path_text = _history_path_text(record, key)
        if not path_text:
            return
        path = Path(path_text)
        if not path.exists():
            QMessageBox.warning(self, f"{label}不存在", f"{label}不存在：\n{path}")
            self._refresh_history()
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not opened:
            QMessageBox.warning(self, f"无法打开{label}", f"无法打开{label}：\n{path}")

    @Slot(int, int)
    def _open_history_csv_at_row(self, row: int, column: int) -> None:
        if column == HISTORY_COLUMN_ACTION:
            return
        if row < 0 or row >= len(self.history_records):
            return
        self.history_table.selectRow(row)
        self._open_history_csv(self.history_records[row])

    def _open_history_csv(self, record: dict[str, object]) -> None:
        path = latest_result_csv_path(self.settings.path.parent / "reports")
        try:
            write_history_record_csv(path, record)
        except ValueError:
            path_text = _record_text(record, "result_csv")
            if not path_text:
                QMessageBox.warning(self, "无法生成 CSV 文件", "这条历史记录缺少任务明细，无法生成 CSV。")
                return
            path = Path(path_text)
        except OSError as exc:
            QMessageBox.warning(self, "CSV 写入失败", f"无法生成 CSV 文件：\n{exc}")
            return
        if not path.exists():
            QMessageBox.warning(self, "CSV 文件不存在", f"CSV 文件不存在：\n{path}")
            self._refresh_history()
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not opened:
            QMessageBox.warning(self, "无法打开 CSV 文件", f"无法打开 CSV 文件：\n{path}")

    def _set_item(self, table: QTableWidget, row: int, column: int, value: str) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        if value:
            item.setToolTip(value)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, column, item)
        return item

    def _style_task_item(self, item: QTableWidgetItem, column: int, task: FrameTask) -> None:
        row_color = TASK_ROW_COLORS.get(task.status)
        if row_color:
            item.setBackground(QColor(row_color))
        if column in {
            TASK_COLUMN_STATUS,
            TASK_COLUMN_DURATION,
            TASK_COLUMN_FPS,
            TASK_COLUMN_TOTAL_FRAMES,
            TASK_COLUMN_RESOLUTION,
            TASK_COLUMN_AUDIO,
        }:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if column == TASK_COLUMN_STATUS:
            background, foreground = TASK_STATUS_COLORS[task.status]
            item.setBackground(QColor(background))
            item.setForeground(QColor(foreground))
        elif column == TASK_COLUMN_OUTPUT_VIDEO and task.removed_video_path:
            item.setBackground(QColor("#e6f6ed"))
            item.setForeground(QColor("#176b35"))
        elif column == TASK_COLUMN_MESSAGE and task.status == TaskStatus.FAILED:
            item.setForeground(QColor("#9f1d1d"))


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


def _format_resolution(width: int | None, height: int | None) -> str:
    if width is None or height is None:
        return "未知"
    return f"{width}x{height}"


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


def _record_text(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    return "" if value is None else str(value)


def _format_history_time(value: str) -> str:
    if not value:
        return ""
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    return timestamp.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


def _history_path_text(record: dict[str, object], key: str) -> str:
    path_text = _record_text(record, key)
    if path_text:
        return path_text
    if key == "output_dir":
        return _record_text(record, "video_output_dir")
    return ""


def _history_path_exists(record: dict[str, object], key: str) -> bool:
    path_text = _history_path_text(record, key)
    return bool(path_text) and Path(path_text).exists()
