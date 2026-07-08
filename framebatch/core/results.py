"""Result report and history persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv
import json

from framebatch import __version__
from framebatch.core.models import FrameTask, NonVideoFile, TaskStatus


SCHEMA_VERSION = 1
HISTORY_FILENAME = "history.json"
MAX_HISTORY_RUNS = 500


@dataclass(frozen=True, slots=True)
class ResultPaths:
    result_json: Path
    result_csv: Path


def make_run_id(started_at: datetime) -> str:
    return started_at.strftime("%Y%m%d_%H%M%S_%f")


def write_result_files(
    *,
    source_dir: Path,
    cover_output_dir: Path,
    video_output_dir: Path,
    history_dir: Path,
    started_at: datetime,
    finished_at: datetime,
    default_frame: int,
    tasks: list[FrameTask],
    candidate_videos: list[NonVideoFile],
    non_videos: list[NonVideoFile],
) -> ResultPaths:
    cover_output_dir.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id(started_at)
    result_paths = ResultPaths(
        result_json=cover_output_dir / "result.json",
        result_csv=cover_output_dir / "result.csv",
    )
    payload = build_result_payload(
        run_id=run_id,
        source_dir=source_dir,
        cover_output_dir=cover_output_dir,
        video_output_dir=video_output_dir,
        started_at=started_at,
        finished_at=finished_at,
        default_frame=default_frame,
        tasks=tasks,
        candidate_videos=candidate_videos,
        non_videos=non_videos,
    )

    with result_paths.result_json.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")

    write_result_csv(result_paths.result_csv, tasks)
    append_history(history_dir, payload, result_paths)
    return result_paths


def build_result_payload(
    *,
    run_id: str,
    source_dir: Path,
    cover_output_dir: Path,
    video_output_dir: Path,
    started_at: datetime,
    finished_at: datetime,
    default_frame: int,
    tasks: list[FrameTask],
    candidate_videos: list[NonVideoFile],
    non_videos: list[NonVideoFile],
) -> dict[str, object]:
    summary = summarize_tasks(tasks, candidate_videos, non_videos)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "app_version": __version__,
        "source_dir": str(source_dir),
        "cover_output_dir": str(cover_output_dir),
        "video_output_dir": str(video_output_dir),
        "output_dir": str(cover_output_dir),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "default_frame": default_frame,
        "summary": summary,
        "tasks": [_task_to_record(task) for task in tasks],
        "candidate_video_files": [_non_video_to_record(item) for item in candidate_videos],
        "non_video_files": [_non_video_to_record(item) for item in non_videos],
    }


def write_result_csv(path: Path, tasks: list[FrameTask]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "status",
                "source_video",
                "frame_user_index",
                "black_frame_status",
                "cover_path",
                "video_path",
                "error_code",
                "message",
                "duration_ms",
            ],
        )
        writer.writeheader()
        for task in tasks:
            writer.writerow(
                {
                    "status": task.status.value,
                    "source_video": task.video.path,
                    "frame_user_index": task.config.frame_user_index,
                    "black_frame_status": task.black_frame_status.value,
                    "cover_path": task.cover_path or "",
                    "video_path": task.removed_video_path or "",
                    "error_code": task.error_code or "",
                    "message": task.message,
                    "duration_ms": "",
                }
            )


def append_history(
    history_dir: Path,
    result_payload: dict[str, object],
    result_paths: ResultPaths,
) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / HISTORY_FILENAME
    history = _load_history(history_path)
    summary = result_payload["summary"]
    assert isinstance(summary, dict)
    record = {
        "run_id": result_payload["run_id"],
        "source_dir": result_payload["source_dir"],
        "cover_output_dir": result_payload["cover_output_dir"],
        "video_output_dir": result_payload["video_output_dir"],
        "output_dir": result_payload["output_dir"],
        "started_at": result_payload["started_at"],
        "finished_at": result_payload["finished_at"],
        "task_count": summary["task_count"],
        "success_count": summary["success_count"],
        "failed_count": summary["failed_count"],
        "canceled_count": summary["canceled_count"],
        "skipped_count": summary["skipped_count"],
        "result_json": str(result_paths.result_json),
        "result_csv": str(result_paths.result_csv),
    }
    runs = history["runs"]
    assert isinstance(runs, list)
    runs.insert(0, record)
    del runs[MAX_HISTORY_RUNS:]
    with history_path.open("w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return history_path


def summarize_tasks(
    tasks: list[FrameTask],
    candidate_videos: list[NonVideoFile],
    non_videos: list[NonVideoFile],
) -> dict[str, int]:
    return {
        "total_files": len(tasks) + len(candidate_videos) + len(non_videos),
        "video_count": len(tasks),
        "candidate_video_count": len(candidate_videos),
        "non_video_count": len(non_videos),
        "task_count": len(tasks),
        "success_count": _count_status(tasks, TaskStatus.SUCCESS),
        "failed_count": _count_status(tasks, TaskStatus.FAILED),
        "canceled_count": _count_status(tasks, TaskStatus.CANCELED),
        "skipped_count": _count_status(tasks, TaskStatus.SKIPPED),
    }


def _task_to_record(task: FrameTask) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "source_video": task.video.path,
        "frame_user_index": task.config.frame_user_index,
        "frame_zero_based": task.config.frame_zero_based,
        "status": task.status.value,
        "black_frame_status": task.black_frame_status.value,
        "cover_path": task.cover_path,
        "video_path": task.removed_video_path,
        "error_code": task.error_code,
        "message": task.message,
        "duration_seconds": task.video.duration_seconds,
        "frame_rate": task.video.frame_rate,
        "total_frames": task.video.total_frames,
        "has_audio": task.video.has_audio,
        "duration_ms": None,
    }


def _non_video_to_record(item: NonVideoFile) -> dict[str, str]:
    return {"path": item.path, "reason": item.reason}


def _count_status(tasks: list[FrameTask], status: TaskStatus) -> int:
    return sum(1 for task in tasks if task.status == status)


def _load_history(history_path: Path) -> dict[str, object]:
    if not history_path.exists():
        return {"schema_version": SCHEMA_VERSION, "runs": []}
    try:
        with history_path.open("r", encoding="utf-8") as file:
            history = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "runs": []}

    if not isinstance(history, dict) or not isinstance(history.get("runs"), list):
        return {"schema_version": SCHEMA_VERSION, "runs": []}
    history["schema_version"] = SCHEMA_VERSION
    return history
