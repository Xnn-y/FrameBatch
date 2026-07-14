from pathlib import Path

from framebatch.ffmpeg import locator
from framebatch.ffmpeg.locator import locate_ffmpeg


def assert_same_path(actual: Path | None, expected: Path) -> None:
    assert actual is not None
    assert actual == expected or actual.samefile(expected)


def test_locate_ffmpeg_uses_configured_directory() -> None:
    runtime = Path(__file__).parent / ".runtime" / "locator_configured"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "ffmpeg.exe").write_text("", encoding="utf-8")
    (runtime / "ffprobe.exe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(configured_ffmpeg_path=str(runtime))

    assert location.is_available is True
    assert location.source == "configured"
    assert_same_path(location.ffmpeg_path, runtime / "ffmpeg.exe")
    assert_same_path(location.ffprobe_path, runtime / "ffprobe.exe")


def test_locate_ffmpeg_uses_macos_configured_directory(monkeypatch) -> None:
    monkeypatch.setattr(locator.sys, "platform", "darwin")
    runtime = Path(__file__).parent / ".runtime" / "locator_configured_macos"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "ffmpeg").write_text("", encoding="utf-8")
    (runtime / "ffprobe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(configured_ffmpeg_path=str(runtime))

    assert location.is_available is True
    assert location.source == "configured"
    assert_same_path(location.ffmpeg_path, runtime / "ffmpeg")
    assert_same_path(location.ffprobe_path, runtime / "ffprobe")


def test_locate_ffmpeg_uses_macos_configured_executable(monkeypatch) -> None:
    monkeypatch.setattr(locator.sys, "platform", "darwin")
    runtime = Path(__file__).parent / ".runtime" / "locator_configured_macos_file"
    runtime.mkdir(parents=True, exist_ok=True)
    ffmpeg_path = runtime / "ffmpeg"
    ffmpeg_path.write_text("", encoding="utf-8")
    (runtime / "ffprobe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(configured_ffmpeg_path=str(ffmpeg_path))

    assert location.is_available is True
    assert location.source == "configured"
    assert_same_path(location.ffmpeg_path, ffmpeg_path)
    assert_same_path(location.ffprobe_path, runtime / "ffprobe")


def test_locate_ffmpeg_uses_bundled_path_when_present() -> None:
    app_root = Path(__file__).parent / ".runtime" / "bundled_app"
    bin_dir = app_root / "tools" / "ffmpeg" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "ffmpeg.exe").write_text("", encoding="utf-8")
    (bin_dir / "ffprobe.exe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(app_root=app_root)

    assert location.is_available is True
    assert location.source == "bundled"
    assert_same_path(location.ffmpeg_path, bin_dir / "ffmpeg.exe")
    assert_same_path(location.ffprobe_path, bin_dir / "ffprobe.exe")


def test_locate_ffmpeg_uses_macos_bundled_path(monkeypatch) -> None:
    monkeypatch.setattr(locator.sys, "platform", "darwin")
    app_root = Path(__file__).parent / ".runtime" / "bundled_macos_app"
    bin_dir = app_root / "tools" / "ffmpeg" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "ffmpeg").write_text("", encoding="utf-8")
    (bin_dir / "ffprobe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(app_root=app_root)

    assert location.is_available is True
    assert location.source == "bundled"
    assert_same_path(location.ffmpeg_path, bin_dir / "ffmpeg")
    assert_same_path(location.ffprobe_path, bin_dir / "ffprobe")


def test_locate_ffmpeg_uses_flat_bundled_path_when_present() -> None:
    app_root = Path(__file__).parent / ".runtime" / "bundled_flat_app"
    bin_dir = app_root / "tools" / "ffmpeg"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "ffmpeg.exe").write_text("", encoding="utf-8")
    (bin_dir / "ffprobe.exe").write_text("", encoding="utf-8")

    location = locate_ffmpeg(app_root=app_root)

    assert location.is_available is True
    assert location.source == "bundled"
    assert_same_path(location.ffmpeg_path, bin_dir / "ffmpeg.exe")
    assert_same_path(location.ffprobe_path, bin_dir / "ffprobe.exe")


def test_locate_ffmpeg_uses_pyinstaller_resource_root(monkeypatch, tmp_path: Path) -> None:
    resource_root = tmp_path / "_internal"
    bin_dir = resource_root / "tools" / "ffmpeg"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ffmpeg.exe").write_text("", encoding="utf-8")
    (bin_dir / "ffprobe.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(locator.sys, "_MEIPASS", str(resource_root), raising=False)

    location = locate_ffmpeg(app_root=tmp_path / "app")

    assert location.is_available is True
    assert location.source == "bundled"
    assert_same_path(location.ffmpeg_path, bin_dir / "ffmpeg.exe")
    assert_same_path(location.ffprobe_path, bin_dir / "ffprobe.exe")
