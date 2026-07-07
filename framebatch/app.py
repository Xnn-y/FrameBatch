"""Application bootstrap.

PySide6 is imported lazily so non-UI modules and tests can run before the GUI
dependency is installed.
"""

from __future__ import annotations


def run() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is not installed. Install development dependencies with "
            'python -m pip install -e ".[dev]".'
        ) from exc

    from framebatch.config.settings import SettingsStore
    from framebatch.ui.main_window import MainWindow

    app = QApplication([])
    settings = SettingsStore.load()
    window = MainWindow(settings=settings)
    window.show()
    return app.exec()
