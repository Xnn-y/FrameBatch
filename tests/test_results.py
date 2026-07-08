from datetime import datetime, timezone
from pathlib import Path
import csv
import json

from framebatch.core.models import (
    BlackFrameStatus,
    FrameTask,
    NonVideoFile,
    TaskConfig,
    TaskStatus,
    VideoFile,
)
from framebatch.core.results import write_result_files


def test_write_result_files_creates_json_csv_and_history(tmp_path: Path) -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(
            path="D:/input/episode01.mp4",
            duration_seconds=12.5,
            frame_rate=25.0,
            total_frames=313,
            has_audio=True,
        ),
        config=TaskConfig(frame_user_index=2, output_stem="episode01"),
        status=TaskStatus.SUCCESS,
        black_frame_status=BlackFrameStatus.OK,
        cover_path=str(tmp_path / "covers" / "episode01.jpg"),
        removed_video_path=str(tmp_path / "videos" / "episode01.mp4"),
        message="done",
    )
    started_at = datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 7, 8, 10, 1, tzinfo=timezone.utc)

    paths = write_result_files(
        source_dir=Path("D:/input"),
        cover_output_dir=tmp_path / "covers",
        video_output_dir=tmp_path / "videos",
        history_dir=tmp_path / "config",
        started_at=started_at,
        finished_at=finished_at,
        default_frame=2,
        tasks=[task],
        candidate_videos=[NonVideoFile(path="D:/input/broken.mp4", reason="bad file")],
        non_videos=[NonVideoFile(path="D:/input/readme.txt", reason="not video")],
    )

    payload = json.loads(paths.result_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["source_dir"] == str(Path("D:/input"))
    assert payload["cover_output_dir"] == str(tmp_path / "covers")
    assert payload["video_output_dir"] == str(tmp_path / "videos")
    assert payload["summary"]["total_files"] == 3
    assert payload["summary"]["success_count"] == 1
    assert payload["tasks"][0]["source_video"] == "D:/input/episode01.mp4"
    assert payload["tasks"][0]["frame_zero_based"] == 1
    assert payload["candidate_video_files"][0]["path"] == "D:/input/broken.mp4"
    assert payload["non_video_files"][0]["path"] == "D:/input/readme.txt"

    with paths.result_csv.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["status"] == "SUCCESS"
    assert rows[0]["video_path"] == str(tmp_path / "videos" / "episode01.mp4")

    history = json.loads((tmp_path / "config" / "history.json").read_text(encoding="utf-8"))
    assert history["runs"][0]["run_id"] == payload["run_id"]
    assert history["runs"][0]["result_json"] == str(paths.result_json)
    assert history["runs"][0]["task_count"] == 1


def test_write_result_files_prepends_history_runs(tmp_path: Path) -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path="a.mp4"),
        config=TaskConfig(frame_user_index=1),
        status=TaskStatus.FAILED,
        error_code="FAILED",
        message="failed",
    )

    first = write_result_files(
        source_dir=tmp_path / "input",
        cover_output_dir=tmp_path / "covers_1",
        video_output_dir=tmp_path / "videos_1",
        history_dir=tmp_path / "config",
        started_at=datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 10, 1, tzinfo=timezone.utc),
        default_frame=1,
        tasks=[task],
        candidate_videos=[],
        non_videos=[],
    )
    second = write_result_files(
        source_dir=tmp_path / "input",
        cover_output_dir=tmp_path / "covers_2",
        video_output_dir=tmp_path / "videos_2",
        history_dir=tmp_path / "config",
        started_at=datetime(2026, 7, 8, 11, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 11, 1, tzinfo=timezone.utc),
        default_frame=1,
        tasks=[task],
        candidate_videos=[],
        non_videos=[],
    )

    first_payload = json.loads(first.result_json.read_text(encoding="utf-8"))
    second_payload = json.loads(second.result_json.read_text(encoding="utf-8"))
    history = json.loads((tmp_path / "config" / "history.json").read_text(encoding="utf-8"))

    assert [run["run_id"] for run in history["runs"]] == [
        second_payload["run_id"],
        first_payload["run_id"],
    ]
