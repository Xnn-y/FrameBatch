from datetime import datetime, timezone
from pathlib import Path
import csv
import json

from framebatch.core import results
from framebatch.core.models import FrameTask, NonVideoFile, TaskConfig, TaskStatus, VideoFile
from framebatch.core.results import clear_history_runs, default_report_root_dir, delete_history_run
from framebatch.core.results import latest_result_csv_path, load_history_runs
from framebatch.core.results import write_history_record_csv, write_result_files


def _successful_task(tmp_path: Path) -> FrameTask:
    return FrameTask(
        task_id="task_0001",
        video=VideoFile(
            path="D:/input/episode01.mp4",
            duration_seconds=12.5,
            frame_rate=25.0,
            total_frames=313,
            width=720,
            height=1280,
            has_audio=True,
        ),
        config=TaskConfig(frame_user_index=1, output_stem="episode01"),
        status=TaskStatus.SUCCESS,
        cover_path=str(tmp_path / "cover.jpg"),
        removed_video_path=str(tmp_path / "videos" / "episode01.mp4"),
        message="done",
    )


def test_write_result_files_creates_single_csv_and_history(tmp_path: Path) -> None:
    task = _successful_task(tmp_path)
    started_at = datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 7, 8, 10, 1, tzinfo=timezone.utc)

    paths = write_result_files(
        source_dir=Path("D:/input"),
        cover_image_path=tmp_path / "cover.jpg",
        output_dir=tmp_path / "videos",
        report_root_dir=tmp_path / "reports",
        history_dir=tmp_path / "config",
        started_at=started_at,
        finished_at=finished_at,
        tasks=[task],
        candidate_videos=[NonVideoFile(path="D:/input/broken.mp4", reason="bad file")],
        non_videos=[NonVideoFile(path="D:/input/readme.txt", reason="not video")],
    )

    assert paths.result_csv == tmp_path / "reports" / "result.csv"
    assert paths.result_json == tmp_path / "config" / "history.json"
    assert sorted(path.name for path in (tmp_path / "reports").iterdir()) == ["result.csv"]

    with paths.result_csv.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert list(rows[0]) == [
        "处理状态",
        "源视频",
        "封面图片",
        "输出视频",
        "时长",
        "帧率",
        "总帧数",
        "分辨率",
        "音频",
        "说明",
    ]
    assert rows[0]["处理状态"] == "成功"
    assert rows[0]["源视频"] == "episode01.mp4"
    assert rows[0]["封面图片"] == "cover.jpg"
    assert rows[0]["输出视频"] == "episode01.mp4"
    assert rows[0]["分辨率"] == "720x1280"
    assert rows[0]["时长"] == "0:12"

    history = json.loads((tmp_path / "config" / "history.json").read_text(encoding="utf-8"))
    run = history["runs"][0]
    assert run["source_dir"] == str(Path("D:/input"))
    assert run["cover_image_path"] == str(tmp_path / "cover.jpg")
    assert run["output_dir"] == str(tmp_path / "videos")
    assert run["task_count"] == 1
    assert run["success_count"] == 1
    assert run["result_csv"] == str(paths.result_csv)
    assert run["tasks"][0]["source_video"] == "D:/input/episode01.mp4"
    assert "frame_zero_based" not in run["tasks"][0]


def test_write_result_files_prepends_history_runs_and_overwrites_csv(tmp_path: Path) -> None:
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
        cover_image_path=tmp_path / "cover_1.jpg",
        output_dir=tmp_path / "videos_1",
        report_root_dir=tmp_path / "reports",
        history_dir=tmp_path / "config",
        started_at=datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 10, 1, tzinfo=timezone.utc),
        tasks=[task],
        candidate_videos=[],
        non_videos=[],
    )
    first_run_id = load_history_runs(tmp_path / "config")[0]["run_id"]

    second = write_result_files(
        source_dir=tmp_path / "input",
        cover_image_path=tmp_path / "cover_2.jpg",
        output_dir=tmp_path / "videos_2",
        report_root_dir=tmp_path / "reports",
        history_dir=tmp_path / "config",
        started_at=datetime(2026, 7, 8, 11, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 11, 1, tzinfo=timezone.utc),
        tasks=[task],
        candidate_videos=[],
        non_videos=[],
    )
    runs = load_history_runs(tmp_path / "config")

    assert first.result_csv == second.result_csv == tmp_path / "reports" / "result.csv"
    assert [run["run_id"] for run in runs] == [runs[0]["run_id"], first_run_id]
    assert runs[0]["cover_image_path"] == str(tmp_path / "cover_2.jpg")


def test_load_history_runs_returns_empty_for_missing_history(tmp_path: Path) -> None:
    assert load_history_runs(tmp_path / "config") == []


def test_default_report_root_dir_uses_appdata_by_default() -> None:
    path = default_report_root_dir()
    assert path.name == "reports"
    assert path.parent.name == "FrameBatch"


def test_default_report_root_dir_is_independent_of_frozen_state(monkeypatch) -> None:
    path_before = default_report_root_dir()
    monkeypatch.setattr(results.sys, "frozen", True, raising=False)
    monkeypatch.setattr(results.sys, "executable", str(Path("C:/fake/FrameBatch.exe")))
    assert default_report_root_dir() == path_before


def test_latest_result_csv_path_uses_report_root() -> None:
    assert latest_result_csv_path(Path("D:/app/reports")) == Path("D:/app/reports/result.csv")


def test_write_result_files_keeps_latest_50_history_runs_and_single_csv(tmp_path: Path) -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path="a.mp4"),
        config=TaskConfig(frame_user_index=1),
        status=TaskStatus.SUCCESS,
    )
    report_root = tmp_path / "reports"
    history_dir = tmp_path / "config"
    result_csv_paths: list[Path] = []

    for index in range(51):
        paths = write_result_files(
            source_dir=tmp_path / "input",
            cover_image_path=tmp_path / "cover.jpg",
            output_dir=tmp_path / "videos",
            report_root_dir=report_root,
            history_dir=history_dir,
            started_at=datetime(2026, 7, 8, 10, index, tzinfo=timezone.utc),
            finished_at=datetime(2026, 7, 8, 10, index, 1, tzinfo=timezone.utc),
            tasks=[task],
            candidate_videos=[],
            non_videos=[],
        )
        result_csv_paths.append(paths.result_csv)

    runs = load_history_runs(history_dir)

    assert len(runs) == 50
    assert set(result_csv_paths) == {report_root / "result.csv"}
    assert sorted(path.name for path in report_root.iterdir()) == ["result.csv"]


def test_write_history_record_csv_exports_selected_run(tmp_path: Path) -> None:
    first_task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path="first.mp4"),
        config=TaskConfig(frame_user_index=1),
        status=TaskStatus.SUCCESS,
        cover_path=str(tmp_path / "cover.jpg"),
        removed_video_path=str(tmp_path / "videos" / "first.mp4"),
    )
    second_task = FrameTask(
        task_id="task_0002",
        video=VideoFile(path="second.mp4"),
        config=TaskConfig(frame_user_index=1),
        status=TaskStatus.SUCCESS,
        cover_path=str(tmp_path / "cover.jpg"),
        removed_video_path=str(tmp_path / "videos" / "second.mp4"),
    )

    write_result_files(
        source_dir=tmp_path / "input",
        cover_image_path=tmp_path / "cover.jpg",
        output_dir=tmp_path / "videos",
        report_root_dir=tmp_path / "reports",
        history_dir=tmp_path / "config",
        started_at=datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 10, 1, tzinfo=timezone.utc),
        tasks=[first_task],
        candidate_videos=[],
        non_videos=[],
    )
    write_result_files(
        source_dir=tmp_path / "input",
        cover_image_path=tmp_path / "cover.jpg",
        output_dir=tmp_path / "videos",
        report_root_dir=tmp_path / "reports",
        history_dir=tmp_path / "config",
        started_at=datetime(2026, 7, 8, 11, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 11, 1, tzinfo=timezone.utc),
        tasks=[second_task],
        candidate_videos=[],
        non_videos=[],
    )

    older_record = load_history_runs(tmp_path / "config")[1]
    csv_path = write_history_record_csv(tmp_path / "reports" / "result.csv", older_record)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["源视频"] == "first.mp4"
    assert rows[0]["封面图片"] == "cover.jpg"
    assert rows[0]["输出视频"] == "first.mp4"


def test_delete_history_run_removes_one_record(tmp_path: Path) -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path="a.mp4"),
        config=TaskConfig(frame_user_index=1),
        status=TaskStatus.SUCCESS,
    )
    history_dir = tmp_path / "config"

    write_result_files(
        source_dir=tmp_path / "input",
        cover_image_path=tmp_path / "cover_1.jpg",
        output_dir=tmp_path / "videos_1",
        report_root_dir=tmp_path / "reports",
        history_dir=history_dir,
        started_at=datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 10, 1, tzinfo=timezone.utc),
        tasks=[task],
        candidate_videos=[],
        non_videos=[],
    )
    write_result_files(
        source_dir=tmp_path / "input",
        cover_image_path=tmp_path / "cover_2.jpg",
        output_dir=tmp_path / "videos_2",
        report_root_dir=tmp_path / "reports",
        history_dir=history_dir,
        started_at=datetime(2026, 7, 8, 11, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 8, 11, 1, tzinfo=timezone.utc),
        tasks=[task],
        candidate_videos=[],
        non_videos=[],
    )
    newest_run_id = str(load_history_runs(history_dir)[0]["run_id"])

    assert delete_history_run(history_dir, newest_run_id) is True
    assert [run["cover_image_path"] for run in load_history_runs(history_dir)] == [
        str(tmp_path / "cover_1.jpg")
    ]
    assert delete_history_run(history_dir, newest_run_id) is False


def test_clear_history_runs_removes_all_records(tmp_path: Path) -> None:
    task = FrameTask(
        task_id="task_0001",
        video=VideoFile(path="a.mp4"),
        config=TaskConfig(frame_user_index=1),
        status=TaskStatus.SUCCESS,
    )
    history_dir = tmp_path / "config"

    for index in range(2):
        write_result_files(
            source_dir=tmp_path / "input",
            cover_image_path=tmp_path / f"cover_{index}.jpg",
            output_dir=tmp_path / f"videos_{index}",
            report_root_dir=tmp_path / "reports",
            history_dir=history_dir,
            started_at=datetime(2026, 7, 8, 10, index, tzinfo=timezone.utc),
            finished_at=datetime(2026, 7, 8, 10, index, 1, tzinfo=timezone.utc),
            tasks=[task],
            candidate_videos=[],
            non_videos=[],
        )

    assert clear_history_runs(history_dir) == 2
    assert load_history_runs(history_dir) == []
