from pathlib import Path

import pytest

from framebatch.core.models import FrameTask, TaskConfig, VideoFile
from framebatch.core.naming import (
    default_cover_output_dir,
    default_output_dir,
    default_video_output_dir,
    normalize_output_stem,
    output_stem_for_task,
    split_output_dirs,
    task_output_paths,
    validate_video_output,
)


def test_default_output_dir_uses_videos_subdirectory() -> None:
    assert default_output_dir(Path("input")) == Path("input") / "videos"
    assert default_cover_output_dir(Path("input")) == Path("input") / "videos"
    assert default_video_output_dir(Path("input")) == Path("input") / "videos"


def test_task_output_paths_use_source_stem() -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path=r"D:\videos\episode01.mp4"),
        config=TaskConfig(frame_user_index=1),
    )

    paths = task_output_paths(task, Path("videos"))

    assert paths.video_path == Path("videos") / "episode01.mp4"


def test_split_output_dirs_keeps_single_video_output_dir() -> None:
    cover_dir, video_dir = split_output_dirs(Path("covers"), Path("videos"))

    assert cover_dir == Path("videos")
    assert video_dir == Path("videos")


def test_output_stem_for_task_uses_numbered_unified_name_for_batches() -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path="episode01.mp4"),
        config=TaskConfig(frame_user_index=1),
    )

    assert output_stem_for_task(task, index=2, total=12, unified_name="batch") == "batch_2"
    assert output_stem_for_task(task, index=1, total=1, unified_name="batch") == "batch"
    assert output_stem_for_task(task, index=1, total=12, unified_name="") == "episode01"


def test_normalize_output_stem_replaces_invalid_filename_chars() -> None:
    assert normalize_output_stem(' a/b:c* ') == "a_b_c_"


def test_validate_video_output_rejects_existing_without_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "episode01.mp4"
    output.write_text("exists", encoding="utf-8")

    with pytest.raises(FileExistsError):
        validate_video_output(output, overwrite=False)


def test_validate_video_output_allows_existing_with_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "episode01.mp4"
    output.write_text("exists", encoding="utf-8")

    validate_video_output(output, overwrite=True)
