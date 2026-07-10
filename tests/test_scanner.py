from pathlib import Path

from framebatch.core.models import VideoFile
from framebatch.core.scanner import scan_directory
from framebatch.ffmpeg.errors import ProbeFailedError


class FakeProber:
    def probe(self, path: Path) -> VideoFile:
        if path.name == "broken.mp4":
            raise ProbeFailedError("未检测到视频流。")
        return VideoFile(
            path=str(path),
            duration_seconds=2.0,
            frame_rate=25.0,
            total_frames=50,
            has_audio=True,
        )


def test_scan_directory_splits_videos_and_non_videos() -> None:
    source = Path(__file__).parent / ".runtime" / "scanner_mixed"
    source.mkdir(parents=True, exist_ok=True)
    (source / "clip.mp4").write_text("fake", encoding="utf-8")
    (source / "broken.mp4").write_text("fake", encoding="utf-8")
    (source / "cover.jpg").write_text("image", encoding="utf-8")
    (source / "notes.txt").write_text("text", encoding="utf-8")

    result = scan_directory(source, FakeProber())

    assert result.total_files == 4
    assert [Path(video.path).name for video in result.videos] == ["clip.mp4"]
    assert [Path(item.path).name for item in result.cover_images] == ["cover.jpg"]
    assert {Path(item.path).name for item in result.candidate_videos} == {"broken.mp4"}
    assert {Path(item.path).name for item in result.non_videos} == {"notes.txt"}


def test_scan_directory_collects_multiple_cover_image_candidates(tmp_path: Path) -> None:
    (tmp_path / "episode01.mp4").write_text("fake", encoding="utf-8")
    (tmp_path / "cover.jpg").write_text("image", encoding="utf-8")
    (tmp_path / "poster.png").write_text("image", encoding="utf-8")

    result = scan_directory(tmp_path, FakeProber())

    assert [Path(item.path).name for item in result.cover_images] == ["cover.jpg", "poster.png"]
    assert result.non_videos == []


def test_scan_directory_marks_candidates_unverified_without_prober() -> None:
    source = Path(__file__).parent / ".runtime" / "scanner_no_prober"
    source.mkdir(parents=True, exist_ok=True)
    (source / "clip.mp4").write_text("fake", encoding="utf-8")

    result = scan_directory(source, prober=None)

    assert result.videos == []
    assert result.candidate_videos[0].reason == "ffprobe 不可用，无法确认该文件是否为有效视频。"
    assert result.non_videos == []


def test_scan_directory_sorts_episode_numbers_naturally() -> None:
    source = Path(__file__).parent / ".runtime" / "scanner_episode_sort"
    source.mkdir(parents=True, exist_ok=True)
    names = [
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第31集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第32集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第3集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第40集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第4集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第5集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第9集.mp4",
    ]
    for name in names:
        (source / name).write_text("fake", encoding="utf-8")

    result = scan_directory(source, FakeProber())

    assert [Path(video.path).name for video in result.videos] == [
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第3集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第4集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第5集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第9集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第31集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第32集.mp4",
        "洗车小工觉醒水鉴，豪门跪求我掌眼-第40集.mp4",
    ]
