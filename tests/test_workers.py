from pathlib import Path

from framebatch.core.models import FrameTask, TaskConfig, VideoFile
from framebatch.ui.workers import CoverWorker


def test_cover_worker_marks_not_started_tasks_skipped_after_cancel(tmp_path: Path) -> None:
    tasks = [
        FrameTask(
            task_id="task_0001",
            video=VideoFile(path="episode01.mp4"),
            config=TaskConfig(frame_user_index=1),
        ),
        FrameTask(
            task_id="task_0002",
            video=VideoFile(path="episode02.mp4"),
            config=TaskConfig(frame_user_index=1),
        ),
    ]
    worker = CoverWorker(
        tasks,
        Path("ffmpeg.exe"),
        tmp_path / "covers",
        tmp_path / "videos",
        unified_name="",
        overwrite=False,
    )
    finished_tasks: list[tuple[int, bool, str, str, str, str]] = []
    worker.task_finished.connect(lambda *args: finished_tasks.append(args))

    worker.cancel()
    worker.run()

    assert [task[4] for task in finished_tasks] == ["TASK_SKIPPED", "TASK_SKIPPED"]
