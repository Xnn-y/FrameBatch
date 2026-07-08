from pathlib import Path
import json

from framebatch.config.settings import SettingsStore


def test_settings_round_trip(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    store = SettingsStore.load(settings_path)

    store.update(
        last_input_dir="D:/input",
        last_output_dir="D:/input/covers",
        last_cover_output_dir="D:/input/covers",
        last_video_output_dir="D:/input/videos",
        unified_output_name="episode",
        default_frame=25,
        overwrite_outputs=True,
    )
    store.save()

    loaded = SettingsStore.load(settings_path)

    assert loaded.settings.last_input_dir == "D:/input"
    assert loaded.settings.last_output_dir == "D:/input/covers"
    assert loaded.settings.last_cover_output_dir == "D:/input/covers"
    assert loaded.settings.last_video_output_dir == "D:/input/videos"
    assert loaded.settings.unified_output_name == "episode"
    assert loaded.settings.default_frame == 25
    assert loaded.settings.overwrite_outputs is True


def test_settings_migrates_legacy_single_output_dir_to_split_dirs(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"last_output_dir": "D:/input/covers"}),
        encoding="utf-8",
    )

    loaded = SettingsStore.load(settings_path)

    assert Path(loaded.settings.last_cover_output_dir or "") == Path("D:/input/covers")
    assert Path(loaded.settings.last_video_output_dir or "") == Path("D:/input/videos")
