from pathlib import Path
import subprocess

import pytest

from framebatch.ffmpeg.cancel import CancelToken
from framebatch.ffmpeg.cover import CoverExtractor
from framebatch.ffmpeg.errors import FFmpegError


def test_cover_extractor_builds_ffmpeg_command_and_returns_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_command: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured_command.extend(command)
        Path(command[-1]).write_bytes(b"jpg")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    output = tmp_path / "cover.jpg"
    extractor = CoverExtractor(Path("ffmpeg.exe"), timeout_seconds=5)

    result = extractor.extract(Path("video.mp4"), 24, output, overwrite=False)

    assert result.cover_path == output
    assert captured_command[:6] == ["ffmpeg.exe", "-v", "error", "-n", "-i", "video.mp4"]
    assert "select=eq(n\\,24)" in captured_command
    assert captured_command[-1] == str(output)


def test_cover_extractor_uses_overwrite_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_command: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured_command.extend(command)
        Path(command[-1]).write_bytes(b"jpg")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    CoverExtractor(Path("ffmpeg.exe")).extract(
        Path("video.mp4"),
        0,
        tmp_path / "cover.jpg",
        overwrite=True,
    )

    assert "-y" in captured_command
    assert "-n" not in captured_command


def test_cover_extractor_reports_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    extractor = CoverExtractor(Path("ffmpeg.exe"), timeout_seconds=1)

    with pytest.raises(FFmpegError) as excinfo:
        extractor.extract(Path("video.mp4"), 0, tmp_path / "cover.jpg", overwrite=False)

    assert excinfo.value.code == "COVER_EXTRACT_TIMEOUT"


def test_cover_extractor_honors_cancel_token(tmp_path: Path) -> None:
    token = CancelToken()
    token.cancel()
    extractor = CoverExtractor(Path("ffmpeg.exe"), timeout_seconds=1)

    with pytest.raises(FFmpegError) as excinfo:
        extractor.extract(
            Path("video.mp4"),
            0,
            tmp_path / "cover.jpg",
            overwrite=False,
            cancel_token=token,
        )

    assert excinfo.value.code == "OPERATION_CANCELED"
