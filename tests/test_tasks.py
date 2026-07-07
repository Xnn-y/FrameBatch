from framebatch.core.models import BlackFrameStatus, TaskStatus, VideoFile
from framebatch.core.tasks import can_check_black_frame, create_frame_tasks, update_task_frame


def test_create_frame_tasks_applies_default_frame() -> None:
    videos = [
        VideoFile(path="a.mp4", total_frames=100),
        VideoFile(path="b.mp4", total_frames=50),
    ]

    tasks = create_frame_tasks(videos, default_frame=25)

    assert [task.config.frame_user_index for task in tasks] == [25, 25]
    assert [task.config.frame_zero_based for task in tasks] == [24, 24]
    assert all(task.status == TaskStatus.READY for task in tasks)


def test_create_frame_tasks_warns_when_frame_exceeds_total() -> None:
    tasks = create_frame_tasks([VideoFile(path="a.mp4", total_frames=10)], default_frame=25)

    assert tasks[0].status == TaskStatus.WARNING
    assert "目标帧超过视频总帧数" in tasks[0].message
    assert can_check_black_frame(tasks[0]) is False


def test_update_task_frame_resets_black_frame_status() -> None:
    task = create_frame_tasks([VideoFile(path="a.mp4", total_frames=100)], default_frame=25)[0]
    task.black_frame_status = BlackFrameStatus.SUSPECTED_BLACK

    update_task_frame(task, 30)

    assert task.config.frame_user_index == 30
    assert task.config.frame_zero_based == 29
    assert task.black_frame_status == BlackFrameStatus.NOT_CHECKED
    assert task.status == TaskStatus.READY


def test_can_check_black_frame_allows_warning_from_suspected_black() -> None:
    task = create_frame_tasks([VideoFile(path="a.mp4", total_frames=100)], default_frame=25)[0]
    task.black_frame_status = BlackFrameStatus.SUSPECTED_BLACK
    task.status = TaskStatus.WARNING
    task.message = "疑似黑屏帧，建议修改目标帧后再处理。"

    assert can_check_black_frame(task) is True
