from pathlib import Path

import pytest

from framebatch.core.models import FrameTask, TaskConfig, VideoFile
from framebatch.core.naming import (
    default_cover_output_dir,
    default_output_dir,
    default_video_output_dir,
    normalize_output_stem,
    output_stem_for_task,
    task_output_paths,
    validate_cover_output,
)


def test_default_output_dir_uses_covers_subdirectory() -> None:
    assert default_output_dir(Path("input")) == Path("input") / "covers"
    assert default_cover_output_dir(Path("input")) == Path("input") / "covers"
    assert default_video_output_dir(Path("input")) == Path("input") / "videos"


def test_task_output_paths_use_source_stem_in_split_dirs() -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path=r"D:\videos\episode01.mp4"),
        config=TaskConfig(frame_user_index=25),
    )

    paths = task_output_paths(task, Path("covers"), Path("videos"))

    assert paths.cover_path == Path("covers") / "episode01.jpg"
    assert paths.removed_video_path == Path("videos") / "episode01.mp4"


def test_output_stem_for_task_uses_numbered_unified_name_for_batches() -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path="episode01.mp4"),
        config=TaskConfig(frame_user_index=25),
    )

    assert output_stem_for_task(task, index=2, total=12, unified_name="batch") == "batch_0002"
    assert output_stem_for_task(task, index=1, total=1, unified_name="batch") == "batch"
    assert output_stem_for_task(task, index=1, total=12, unified_name="") == "episode01"


def test_normalize_output_stem_replaces_invalid_filename_chars() -> None:
    assert normalize_output_stem(' a/b:c* ') == "a_b_c_"


def test_validate_cover_output_rejects_existing_without_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "cover.jpg"
    output.write_text("exists", encoding="utf-8")

    with pytest.raises(FileExistsError):
        validate_cover_output(output, overwrite=False)


def test_validate_cover_output_allows_existing_with_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "cover.jpg"
    output.write_text("exists", encoding="utf-8")

    validate_cover_output(output, overwrite=True)
