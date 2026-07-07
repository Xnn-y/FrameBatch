"""User settings persistence for FrameBatch."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os


APP_NAME = "FrameBatch"
SETTINGS_FILENAME = "settings.json"


@dataclass(slots=True)
class UserSettings:
    last_input_dir: str | None = None
    last_output_dir: str | None = None
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    default_frame: int = 1
    overwrite_outputs: bool = False


class SettingsStore:
    """Read and write user settings from the per-user app config directory."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()
        self.settings = UserSettings()

    @classmethod
    def default_path(cls) -> Path:
        base = os.environ.get("FRAMEBATCH_CONFIG_DIR")
        if base:
            return Path(base) / SETTINGS_FILENAME

        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME / SETTINGS_FILENAME

        return Path.home() / ".framebatch" / SETTINGS_FILENAME

    @classmethod
    def load(cls, path: Path | None = None) -> "SettingsStore":
        store = cls(path)
        if not store.path.exists():
            return store

        with store.path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        store.settings = UserSettings(
            last_input_dir=raw.get("last_input_dir"),
            last_output_dir=raw.get("last_output_dir"),
            ffmpeg_path=raw.get("ffmpeg_path"),
            ffprobe_path=raw.get("ffprobe_path"),
            default_frame=int(raw.get("default_frame", 1)),
            overwrite_outputs=bool(raw.get("overwrite_outputs", False)),
        )
        return store

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(asdict(self.settings), file, ensure_ascii=False, indent=2)

    def update(self, **changes: object) -> None:
        for key, value in changes.items():
            if not hasattr(self.settings, key):
                raise KeyError(f"Unknown setting: {key}")
            setattr(self.settings, key, value)
