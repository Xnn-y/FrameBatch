from pathlib import Path

from framebatch.ffmpeg.locator import locate_ffmpeg


def test_locate_ffmpeg_uses_configured_directory() -> None:
    runtime = Path(__file__).parent / ".runtime" / "locator_configured"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "ffmpeg.exe").write_text("", encoding="utf-8")
    (runtime / "ffprobe.exe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(configured_ffmpeg_path=str(runtime))

    assert location.is_available is True
    assert location.source == "configured"
    assert location.ffmpeg_path == runtime / "ffmpeg.exe"
    assert location.ffprobe_path == runtime / "ffprobe.exe"


def test_locate_ffmpeg_uses_bundled_path_when_present() -> None:
    app_root = Path(__file__).parent / ".runtime" / "bundled_app"
    bin_dir = app_root / "tools" / "ffmpeg" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "ffmpeg.exe").write_text("", encoding="utf-8")
    (bin_dir / "ffprobe.exe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(app_root=app_root)

    assert location.is_available is True
    assert location.source == "bundled"
    assert location.ffmpeg_path == bin_dir / "ffmpeg.exe"
    assert location.ffprobe_path == bin_dir / "ffprobe.exe"


def test_locate_ffmpeg_uses_flat_bundled_path_when_present() -> None:
    app_root = Path(__file__).parent / ".runtime" / "bundled_flat_app"
    bin_dir = app_root / "tools" / "ffmpeg"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "ffmpeg.exe").write_text("", encoding="utf-8")
    (bin_dir / "ffprobe.exe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(app_root=app_root)

    assert location.is_available is True
    assert location.source == "bundled"
    assert location.ffmpeg_path == bin_dir / "ffmpeg.exe"
    assert location.ffprobe_path == bin_dir / "ffprobe.exe"
