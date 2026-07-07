from pathlib import Path
import subprocess

import pytest

from framebatch.ffmpeg.errors import FFmpegError
from framebatch.ffmpeg.remove_frame import FrameRemovalRenderer


def test_frame_removal_renderer_builds_video_only_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_command: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured_command.extend(command)
        Path(command[-1]).write_bytes(b"mp4")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    output = tmp_path / "out.mp4"

    result = FrameRemovalRenderer(Path("ffmpeg.exe")).render(
        Path("video.mp4"),
        24,
        output,
        has_audio=False,
        overwrite=False,
    )

    assert result.video_path == output
    assert captured_command[:6] == ["ffmpeg.exe", "-v", "error", "-n", "-i", "video.mp4"]
    assert "select=not(eq(n\\,24)),setpts=N/FRAME_RATE/TB" in captured_command
    assert "-an" in captured_command
    assert "-c:v" in captured_command
    assert captured_command[-1] == str(output)


def test_frame_removal_renderer_falls_back_to_aac_for_audio(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        commands.append(command)
        if len(commands) == 1:
            return subprocess.CompletedProcess(command, 1, b"", b"audio copy failed")
        Path(command[-1]).write_bytes(b"mp4")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = FrameRemovalRenderer(Path("ffmpeg.exe")).render(
        Path("video.mp4"),
        0,
        tmp_path / "out.mp4",
        has_audio=True,
        overwrite=False,
    )

    assert "音频已降级为 AAC" in result.message
    assert ["-c:a", "copy"] == commands[0][-3:-1]
    assert "-y" in commands[1]
    assert "-c:a" in commands[1]
    assert "aac" in commands[1]


def test_frame_removal_renderer_reports_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    renderer = FrameRemovalRenderer(Path("ffmpeg.exe"), timeout_seconds=1)

    with pytest.raises(FFmpegError) as excinfo:
        renderer.render(Path("video.mp4"), 0, tmp_path / "out.mp4", has_audio=False, overwrite=False)

    assert excinfo.value.code == "VIDEO_RENDER_TIMEOUT"
