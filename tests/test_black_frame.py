from pathlib import Path
import subprocess

import pytest

from framebatch.core.models import BlackFrameStatus
from framebatch.ffmpeg.black_frame import BlackFrameChecker, analyze_ppm_bytes
from framebatch.ffmpeg.errors import FFmpegError


def _ppm(width: int, height: int, pixels: bytes) -> bytes:
    return f"P6\n{width} {height}\n255\n".encode("ascii") + pixels


def test_analyze_ppm_bytes_marks_black_frame() -> None:
    result = analyze_ppm_bytes(_ppm(2, 2, bytes([0, 0, 0] * 4)))

    assert result.status == BlackFrameStatus.SUSPECTED_BLACK
    assert result.average_luma == 0
    assert result.bright_pixel_ratio == 0


def test_analyze_ppm_bytes_marks_normal_frame() -> None:
    result = analyze_ppm_bytes(_ppm(2, 2, bytes([255, 255, 255] * 4)))

    assert result.status == BlackFrameStatus.OK
    assert result.average_luma == pytest.approx(255)
    assert result.bright_pixel_ratio == 1


def test_analyze_ppm_bytes_preserves_pixel_leading_whitespace_values() -> None:
    result = analyze_ppm_bytes(_ppm(1, 1, bytes([10, 10, 10])))

    assert result.status == BlackFrameStatus.SUSPECTED_BLACK
    assert result.average_luma == pytest.approx(10)


def test_analyze_ppm_bytes_rejects_incomplete_pixels() -> None:
    with pytest.raises(ValueError):
        analyze_ppm_bytes(_ppm(2, 2, bytes([0, 0, 0])))


def test_black_frame_checker_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    checker = BlackFrameChecker(Path("ffmpeg.exe"), timeout_seconds=1)

    with pytest.raises(FFmpegError) as excinfo:
        checker.check(Path("video.mp4"), 0)

    assert excinfo.value.code == "BLACK_FRAME_CHECK_TIMEOUT"
    assert "超时" in excinfo.value.message
