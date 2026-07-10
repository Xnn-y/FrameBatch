from pathlib import Path
import subprocess

import pytest

from framebatch.ffmpeg.cancel import CancelToken
from framebatch.ffmpeg.errors import FFmpegError
from framebatch.ffmpeg.remove_frame import PrependCoverRenderer


def test_prepend_cover_renderer_writes_partial_then_promotes_to_final(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured_command: list[str] = []
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured_command.extend(command)
        Path(command[-1]).write_bytes(b"mp4")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    output = tmp_path / "out.mp4"

    result = PrependCoverRenderer(Path("ffmpeg.exe")).render(
        Path("video.mp4"),
        cover,
        output,
        width=1081,
        height=1921,
        frame_rate=25,
        has_audio=False,
        overwrite=False,
    )

    assert result.video_path == output
    assert captured_command[:10] == [
        "ffmpeg.exe",
        "-v",
        "error",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "25",
        "-i",
        str(cover),
    ]
    assert "-filter_complex" in captured_command
    filter_graph = captured_command[captured_command.index("-filter_complex") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=decrease" in filter_graph
    assert "trim=duration=0.04" in filter_graph
    assert "[cover][video]concat=n=2:v=1:a=0[v]" in filter_graph
    assert "-an" in captured_command
    assert Path(captured_command[-1]).name == ".out.partial.mp4"
    assert output.read_bytes() == b"mp4"
    assert not Path(captured_command[-1]).exists()


def test_prepend_cover_renderer_maps_original_audio(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")
    captured_command: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        captured_command.extend(command)
        Path(command[-1]).write_bytes(b"mp4")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = PrependCoverRenderer(Path("ffmpeg.exe")).render(
        Path("video.mp4"),
        cover,
        tmp_path / "out.mp4",
        width=720,
        height=1280,
        frame_rate=30,
        has_audio=True,
        overwrite=True,
    )

    assert result.message == "封面帧插入成功。"
    assert "-y" in captured_command
    audio_map_index = captured_command.index("1:a?") - 1
    assert ["-map", "1:a?", "-c:a", "copy"] == captured_command[audio_map_index : audio_map_index + 4]


def test_prepend_cover_renderer_reports_timeout_and_deletes_partial_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        Path(command[-1]).write_bytes(b"partial")
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)
    renderer = PrependCoverRenderer(Path("ffmpeg.exe"), timeout_seconds=1)

    with pytest.raises(FFmpegError) as excinfo:
        renderer.render(
            Path("video.mp4"),
            cover,
            tmp_path / "out.mp4",
            width=720,
            height=1280,
            frame_rate=30,
            has_audio=False,
            overwrite=False,
        )

    assert excinfo.value.code == "PREPEND_COVER_TIMEOUT"
    assert not (tmp_path / "out.mp4").exists()
    assert not (tmp_path / ".out.partial.mp4").exists()


def test_prepend_cover_renderer_deletes_partial_output_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        Path(command[-1]).write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1, b"", b"failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FFmpegError) as excinfo:
        PrependCoverRenderer(Path("ffmpeg.exe")).render(
            Path("video.mp4"),
            cover,
            tmp_path / "out.mp4",
            width=720,
            height=1280,
            frame_rate=30,
            has_audio=False,
            overwrite=False,
        )

    assert excinfo.value.code == "PREPEND_COVER_FAILED"
    assert not (tmp_path / "out.mp4").exists()
    assert not (tmp_path / ".out.partial.mp4").exists()


def test_prepend_cover_renderer_honors_cancel_token(tmp_path: Path) -> None:
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")
    token = CancelToken()
    token.cancel()
    renderer = PrependCoverRenderer(Path("ffmpeg.exe"), timeout_seconds=1)

    with pytest.raises(FFmpegError) as excinfo:
        renderer.render(
            Path("video.mp4"),
            cover,
            tmp_path / "out.mp4",
            width=720,
            height=1280,
            frame_rate=30,
            has_audio=False,
            overwrite=False,
            cancel_token=token,
        )

    assert excinfo.value.code == "OPERATION_CANCELED"
