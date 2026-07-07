from pathlib import Path

from framebatch.config.settings import SettingsStore


def test_settings_round_trip() -> None:
    settings_path = Path(__file__).parent / ".runtime" / "settings.json"
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
