"""Result report and history persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv
import json
import os
import sys

from framebatch import __version__
from framebatch.core.models import FrameTask, NonVideoFile, TaskStatus


SCHEMA_VERSION = 2
HISTORY_FILENAME = "history.json"
MAX_HISTORY_RUNS = 50
REPORTS_DIRNAME = "reports"
LATEST_RESULT_CSV_FILENAME = "result.csv"

CSV_FIELDNAMES = [
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


@dataclass(frozen=True, slots=True)
class ResultPaths:
    result_json: Path
    result_csv: Path


def make_run_id(started_at: datetime) -> str:
    return started_at.strftime("%Y%m%d_%H%M%S_%f")


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_report_root_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "FrameBatch" / REPORTS_DIRNAME
    return Path.home() / ".framebatch" / REPORTS_DIRNAME


def latest_result_csv_path(report_root_dir: Path | None = None) -> Path:
    return (report_root_dir or default_report_root_dir()) / LATEST_RESULT_CSV_FILENAME


def history_path_for(history_dir: Path) -> Path:
    return history_dir / HISTORY_FILENAME


def load_history_runs(history_dir: Path) -> list[dict[str, object]]:
    history = _load_history(history_path_for(history_dir))
    runs = history["runs"]
    if not isinstance(runs, list):
        return []
    return [run for run in runs if isinstance(run, dict)]


def delete_history_run(history_dir: Path, run_id: str) -> bool:
    history_path = history_path_for(history_dir)
    history = _load_history(history_path)
    runs = history["runs"]
    if not isinstance(runs, list):
        return False

    kept_runs: list[object] = []
    removed_runs: list[object] = []
    for run in runs:
        if isinstance(run, dict) and run.get("run_id") == run_id:
            removed_runs.append(run)
        else:
            kept_runs.append(run)
    if not removed_runs:
        return False

    history["runs"] = kept_runs
    _write_history(history_path, history)
    return True


def clear_history_runs(history_dir: Path) -> int:
    history_path = history_path_for(history_dir)
    history = _load_history(history_path)
    runs = history["runs"]
    if not isinstance(runs, list):
        return 0

    removed_count = len([run for run in runs if isinstance(run, dict)])
    if removed_count == 0 and history_path.exists():
        return 0

    history["runs"] = []
    _write_history(history_path, history)
    return removed_count


def write_result_files(
    *,
    source_dir: Path,
    cover_image_path: Path,
    output_dir: Path,
    report_root_dir: Path | None = None,
    history_dir: Path,
    started_at: datetime,
    finished_at: datetime,
    tasks: list[FrameTask],
    candidate_videos: list[NonVideoFile],
    non_videos: list[NonVideoFile],
) -> ResultPaths:
    run_id = make_run_id(started_at)
    if report_root_dir is None:
        report_root_dir = history_dir / REPORTS_DIRNAME
    result_paths = ResultPaths(
        result_json=history_path_for(history_dir),
        result_csv=latest_result_csv_path(report_root_dir),
    )
    payload = build_result_payload(
        run_id=run_id,
        source_dir=source_dir,
        cover_image_path=cover_image_path,
        output_dir=output_dir,
        started_at=started_at,
        finished_at=finished_at,
        tasks=tasks,
        candidate_videos=candidate_videos,
        non_videos=non_videos,
    )

    write_result_csv(result_paths.result_csv, tasks)
    append_history(history_dir, payload, result_paths)
    return result_paths


def build_result_payload(
    *,
    run_id: str,
    source_dir: Path,
    cover_image_path: Path,
    output_dir: Path,
    started_at: datetime,
    finished_at: datetime,
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
        "cover_image_path": str(cover_image_path),
        "output_dir": str(output_dir),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "summary": summary,
        "tasks": [_task_to_record(task) for task in tasks],
        "candidate_video_files": [_non_video_to_record(item) for item in candidate_videos],
        "non_video_files": [_non_video_to_record(item) for item in non_videos],
    }


def write_result_csv(path: Path, tasks: list[FrameTask]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for task in tasks:
            writer.writerow(_task_to_csv_row(task))


def write_history_record_csv(path: Path, record: dict[str, object]) -> Path:
    tasks = record.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("历史记录缺少任务明细，无法生成 CSV。")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for task in tasks:
            if isinstance(task, dict):
                writer.writerow(_task_record_to_csv_row(task))
    return path


def append_history(
    history_dir: Path,
    result_payload: dict[str, object],
    result_paths: ResultPaths,
) -> Path:
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_path_for(history_dir)
    history = _load_history(history_path)
    summary = result_payload["summary"]
    assert isinstance(summary, dict)
    record = {
        "run_id": result_payload["run_id"],
        "source_dir": result_payload["source_dir"],
        "cover_image_path": result_payload["cover_image_path"],
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
        "tasks": result_payload["tasks"],
    }
    runs = history["runs"]
    assert isinstance(runs, list)
    runs.insert(0, record)
    removed_runs = runs[MAX_HISTORY_RUNS:]
    del runs[MAX_HISTORY_RUNS:]
    _write_history(history_path, history)
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
        "status": task.status.value,
        "cover_path": task.cover_path,
        "video_path": task.removed_video_path,
        "error_code": task.error_code,
        "message": task.message,
        "duration_seconds": task.video.duration_seconds,
        "frame_rate": task.video.frame_rate,
        "total_frames": task.video.total_frames,
        "width": task.video.width,
        "height": task.video.height,
        "has_audio": task.video.has_audio,
    }


def _task_to_csv_row(task: FrameTask) -> dict[str, object]:
    return {
        "处理状态": _format_task_status(task.status),
        "源视频": Path(task.video.path).name,
        "封面图片": Path(task.cover_path).name if task.cover_path else "",
        "输出视频": Path(task.removed_video_path).name if task.removed_video_path else "",
        "时长": _format_duration(task.video.duration_seconds),
        "帧率": _format_number(task.video.frame_rate),
        "总帧数": task.video.total_frames if task.video.total_frames is not None else "未知",
        "分辨率": _format_resolution(task.video.width, task.video.height),
        "音频": "有" if task.video.has_audio else "无",
        "说明": _format_task_message(task),
    }


def _task_record_to_csv_row(task: dict[str, object]) -> dict[str, object]:
    source_video = str(task.get("source_video") or "")
    cover_path = str(task.get("cover_path") or "")
    video_path = str(task.get("video_path") or "")
    return {
        "处理状态": _format_task_status_value(task.get("status")),
        "源视频": Path(source_video).name if source_video else "",
        "封面图片": Path(cover_path).name if cover_path else "",
        "输出视频": Path(video_path).name if video_path else "",
        "时长": _format_duration(_float_or_none(task.get("duration_seconds"))),
        "帧率": _format_number(_float_or_none(task.get("frame_rate"))),
        "总帧数": task.get("total_frames") if task.get("total_frames") is not None else "未知",
        "分辨率": _format_resolution(_int_or_none(task.get("width")), _int_or_none(task.get("height"))),
        "音频": "有" if bool(task.get("has_audio")) else "无",
        "说明": _format_record_message(task),
    }


def _non_video_to_record(item: NonVideoFile) -> dict[str, str]:
    return {"path": item.path, "reason": item.reason}


def _count_status(tasks: list[FrameTask], status: TaskStatus) -> int:
    return sum(1 for task in tasks if task.status == status)


def _format_task_status(status: TaskStatus) -> str:
    labels = {
        TaskStatus.PENDING: "等待",
        TaskStatus.SCANNING: "扫描中",
        TaskStatus.READY: "就绪",
        TaskStatus.WARNING: "需确认",
        TaskStatus.RUNNING: "处理中",
        TaskStatus.SUCCESS: "成功",
        TaskStatus.FAILED: "失败",
        TaskStatus.CANCELED: "已取消",
        TaskStatus.SKIPPED: "已跳过",
    }
    return labels[status]


def _format_task_status_value(value: object) -> str:
    try:
        return _format_task_status(TaskStatus(str(value)))
    except ValueError:
        return str(value or "")


def _format_duration(value: float | None) -> str:
    if value is None:
        return "未知"
    minutes, seconds = divmod(round(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def _format_number(value: float | None) -> str:
    if value is None:
        return "未知"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _format_resolution(width: int | None, height: int | None) -> str:
    if width is None or height is None:
        return "未知"
    return f"{width}x{height}"


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_task_message(task: FrameTask) -> str:
    if task.error_code:
        return f"{task.message}（错误码：{task.error_code}）"
    return task.message


def _format_record_message(task: dict[str, object]) -> str:
    message = str(task.get("message") or "")
    error_code = str(task.get("error_code") or "")
    if error_code:
        return f"{message}（错误码：{error_code}）"
    return message


def _load_history(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "runs": []}
    try:
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "runs": []}
    if not isinstance(loaded, dict):
        return {"schema_version": SCHEMA_VERSION, "runs": []}
    runs = loaded.get("runs")
    if not isinstance(runs, list):
        loaded["runs"] = []
    loaded["schema_version"] = SCHEMA_VERSION
    return loaded


def _write_history(path: Path, history: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)

