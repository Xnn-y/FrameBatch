"""Main application window for the phase 0 shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QVBoxLayout, QWidget

from framebatch.config.settings import SettingsStore


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self.settings = settings
        self.setWindowTitle("FrameBatch")
        self.resize(1040, 720)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Phase 0 shell ready")

        title = QLabel("FrameBatch")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("appTitle")

        subtitle = QLabel("Batch cover extraction and frame-removal workflow")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("appSubtitle")

        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
