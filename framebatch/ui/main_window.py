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
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from framebatch.config.settings import SettingsStore
from framebatch.core.models import BlackFrameStatus, FrameTask, NonVideoFile, TaskStatus
from framebatch.core.scanner import ScanResult
from framebatch.core.tasks import create_frame_tasks, update_task_frame
from framebatch.ffmpeg.black_frame import BlackFrameCheckResult
from framebatch.ffmpeg.locator import FFmpegLocation, locate_ffmpeg
from framebatch.ui.workers import BlackFrameWorker, ScanWorker


TASK_COLUMN_FILE = 0
TASK_COLUMN_FRAME = 1
TASK_COLUMN_BLACK = 2
TASK_COLUMN_STATUS = 3
TASK_COLUMN_DURATION = 4
TASK_COLUMN_FPS = 5
TASK_COLUMN_TOTAL_FRAMES = 6
TASK_COLUMN_AUDIO = 7
TASK_COLUMN_MESSAGE = 8
TASK_COLUMN_PATH = 9


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
        self.tasks: list[FrameTask] = []
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
                "消息",
                "路径",
            ],
            editable=True,
        )
        self.candidate_table = self._create_table(["文件", "未确认原因", "路径"], editable=False)
        self.non_video_table = self._create_table(["文件", "原因", "路径"], editable=False)

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

        task_config_group = QGroupBox("任务配置")
        task_config_layout = QHBoxLayout(task_config_group)
        task_config_layout.addWidget(QLabel("默认目标帧"))
        task_config_layout.addWidget(self.default_frame_spin)
        task_config_layout.addWidget(self.apply_frame_button)
        task_config_layout.addWidget(self.black_check_button)
        task_config_layout.addStretch(1)

        tables_layout = QHBoxLayout()

        task_group = QGroupBox("视频任务")
        task_layout = QVBoxLayout(task_group)
        task_layout.addWidget(self.task_table)

        candidate_group = QGroupBox("候选视频 / 未确认")
        candidate_layout = QVBoxLayout(candidate_group)
        candidate_layout.addWidget(self.candidate_table)

        non_video_group = QGroupBox("其他文件")
        non_video_layout = QVBoxLayout(non_video_group)
        non_video_layout.addWidget(self.non_video_table)

        tables_layout.addWidget(task_group, 4)
        tables_layout.addWidget(candidate_group, 2)
        tables_layout.addWidget(non_video_group, 2)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)
        root_layout.addWidget(header)
        root_layout.addWidget(input_group)
        root_layout.addWidget(ffmpeg_group)
        root_layout.addWidget(task_config_group)
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
        self.apply_frame_button.clicked.connect(self._apply_default_frame_to_all)
        self.black_check_button.clicked.connect(self._start_black_check)

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

        self.settings.update(
            last_input_dir=str(source_dir),
            default_frame=self.default_frame_spin.value(),
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
        self.scan_button.setEnabled(enabled)
        self.ffmpeg_edit.setEnabled(enabled)
        self.browse_ffmpeg_button.setEnabled(enabled)
        self.refresh_ffmpeg_button.setEnabled(enabled)
        self._refresh_task_actions()

    def _set_processing_enabled(self, enabled: bool) -> None:
        self.scan_button.setEnabled(enabled)
        self.task_table.setEnabled(enabled)
        self._refresh_task_actions()

    def _refresh_task_actions(self) -> None:
        has_tasks = bool(self.tasks)
        can_interact = has_tasks and not self.is_busy
        can_check_black = can_interact and self.ffmpeg_location.ffmpeg_path is not None
        self.apply_frame_button.setEnabled(can_interact)
        self.black_check_button.setEnabled(can_check_black)
        if can_check_black:
            self.black_check_button.setToolTip("检测每个任务目标帧是否疑似黑屏")
        elif has_tasks and self.ffmpeg_location.ffmpeg_path is None:
            self.black_check_button.setToolTip("请先配置 ffmpeg.exe，再检测疑似黑屏")
        elif self.is_busy:
            self.black_check_button.setToolTip("当前任务运行中，请稍候")
        else:
            self.black_check_button.setToolTip("请先扫描出有效视频任务")

    def _clear_tables(self) -> None:
        self.task_table.setRowCount(0)
        self.candidate_table.setRowCount(0)
        self.non_video_table.setRowCount(0)

    def _populate_tasks(self) -> None:
        self.updating_task_table = True
        self.task_table.setRowCount(len(self.tasks))
        for row, task in enumerate(self.tasks):
            self._set_task_row(row, task)
        self.updating_task_table = False

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
            task.message,
            str(path),
        ]
        for column, value in enumerate(values):
            if column == TASK_COLUMN_FRAME:
                self._set_frame_spin(row, task)
            else:
                self._set_item(self.task_table, row, column, value, editable=False)
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
            self._set_item(self.candidate_table, row, 2, str(path), editable=False)

    def _populate_non_videos(self, files: list[NonVideoFile]) -> None:
        self.non_video_table.setRowCount(len(files))
        for row, item in enumerate(files):
            path = Path(item.path)
            self._set_item(self.non_video_table, row, 0, path.name, editable=False)
            self._set_item(self.non_video_table, row, 1, item.reason, editable=False)
            self._set_item(self.non_video_table, row, 2, str(path), editable=False)

    def _set_item(
        self,
        table: QTableWidget,
        row: int,
        column: int,
        value: str,
        *,
        editable: bool,
    ) -> None:
        item = QTableWidgetItem(value)
        flags = item.flags()
        if editable:
            item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
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
