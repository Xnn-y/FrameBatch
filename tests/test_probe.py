from pathlib import Path
import json
import subprocess

import pytest

from framebatch.ffmpeg.errors import ProbeFailedError
from framebatch.ffmpeg.probe import (
    FFprobeVideoProber,
    _parse_dimension,
    _parse_duration,
    _parse_frame_rate,
    _parse_total_frames,
)


def test_parse_video_metadata_prefers_nb_frames() -> None:
    stream = {
        "duration": "4.0",
        "avg_frame_rate": "25/1",
        "nb_frames": "90",
    }

    duration = _parse_duration(stream, {})
    frame_rate = _parse_frame_rate(stream)
    total_frames = _parse_total_frames(stream, duration, frame_rate)

    assert duration == 4.0
    assert frame_rate == 25.0
    assert total_frames == 90


def test_parse_total_frames_falls_back_to_duration_times_rate() -> None:
    stream = {
        "avg_frame_rate": "30000/1001",
        "nb_frames": "N/A",
    }

    total_frames = _parse_total_frames(stream, duration=10.0, frame_rate=_parse_frame_rate(stream))

    assert total_frames == 300


def test_parse_dimension_accepts_positive_integer_values() -> None:
    assert _parse_dimension(1920) == 1920
    assert _parse_dimension("1080") == 1080
    assert _parse_dimension("N/A") is None
    assert _parse_dimension(0) is None


def test_probe_includes_video_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "duration": "2.0",
                "avg_frame_rate": "24/1",
                "nb_frames": "48",
                "width": 1280,
                "height": 720,
            },
            {"codec_type": "audio"},
        ],
        "format": {},
    }

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args[0], 0, json.dumps(payload), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    prober = FFprobeVideoProber(Path("ffprobe.exe"))

    video = prober.probe(Path("video.mp4"))

    assert video.width == 1280
    assert video.height == 720
    assert video.has_audio is True


def test_probe_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    prober = FFprobeVideoProber(Path("ffprobe.exe"), timeout_seconds=1)

    with pytest.raises(ProbeFailedError) as excinfo:
        prober.probe(Path("video.mp4"))

    assert excinfo.value.code == "FFPROBE_FAILED"
    assert "超时" in excinfo.value.message
