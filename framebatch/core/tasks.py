"""Frame task creation and frame-index validation."""

from __future__ import annotations

from framebatch.core.models import BlackFrameStatus, FrameTask, TaskConfig, TaskStatus, VideoFile
from framebatch.core.validators import validate_frame_user_index


def create_frame_tasks(videos: list[VideoFile], default_frame: int) -> list[FrameTask]:
    validate_frame_user_index(default_frame)
    tasks: list[FrameTask] = []
    for index, video in enumerate(videos, start=1):
        task = FrameTask(
            task_id=f"task_{index:04d}",
            video=video,
            config=TaskConfig(frame_user_index=default_frame),
            status=TaskStatus.READY,
        )
        validate_task_frame(task)
        tasks.append(task)
    return tasks


def update_task_frame(task: FrameTask, frame_user_index: int) -> None:
    task.config.frame_user_index = validate_frame_user_index(frame_user_index)
    task.black_frame_status = BlackFrameStatus.NOT_CHECKED
    task.cover_path = None
    task.removed_video_path = None
    task.error_code = None
    validate_task_frame(task)


def validate_task_frame(task: FrameTask) -> None:
    try:
        validate_frame_user_index(task.config.frame_user_index)
    except (TypeError, ValueError) as exc:
        task.status = TaskStatus.FAILED
        task.message = str(exc)
        return

    total_frames = task.video.total_frames
    if total_frames is not None and task.config.frame_user_index > total_frames:
        task.status = TaskStatus.WARNING
        task.message = f"目标帧超过视频总帧数：总帧数 {total_frames}。"
        return

    task.status = TaskStatus.READY
    task.message = ""


def task_frame_error(task: FrameTask) -> str | None:
    try:
        validate_frame_user_index(task.config.frame_user_index)
    except (TypeError, ValueError) as exc:
        return str(exc)

    total_frames = task.video.total_frames
    if total_frames is not None and task.config.frame_user_index > total_frames:
        return f"目标帧超过视频总帧数：总帧数 {total_frames}。"

    return None


def can_check_black_frame(task: FrameTask) -> bool:
    return task_frame_error(task) is None
