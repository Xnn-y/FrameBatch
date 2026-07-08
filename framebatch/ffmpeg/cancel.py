"""Cancellation helpers for long-running FFmpeg subprocesses."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, Lock
import subprocess
import time

from framebatch.ffmpeg.errors import FFmpegError


CANCELED_ERROR_CODE = "OPERATION_CANCELED"
CANCELED_MESSAGE = "抽帧已终止。"


@dataclass(slots=True)
class CancelToken:
    _event: Event = field(default_factory=Event)
    _lock: Lock = field(default_factory=Lock)
    _process: subprocess.Popen[bytes] | None = None

    def cancel(self) -> None:
        self._event.set()
        self.terminate_current_process()

    def is_requested(self) -> bool:
        return self._event.is_set()

    def bind_process(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            self._process = process
            if self._event.is_set():
                _terminate_process(process)

    def clear_process(self, process: subprocess.Popen[bytes]) -> None:
        with self._lock:
            if self._process is process:
                self._process = None

    def terminate_current_process(self) -> None:
        with self._lock:
            process = self._process
        if process is not None:
            _terminate_process(process)


def run_cancelable(
    command: list[str],
    *,
    timeout: int,
    cancel_token: CancelToken | None,
) -> subprocess.CompletedProcess[bytes]:
    if cancel_token is None:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout,
        )

    if cancel_token.is_requested():
        raise FFmpegError(CANCELED_ERROR_CODE, CANCELED_MESSAGE)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    cancel_token.bind_process(process)
    started_at = time.monotonic()
    try:
        while process.poll() is None:
            if cancel_token.is_requested():
                _terminate_process(process)
                raise FFmpegError(CANCELED_ERROR_CODE, CANCELED_MESSAGE)
            if time.monotonic() - started_at > timeout:
                _terminate_process(process)
                raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)
            time.sleep(0.1)

        stdout, stderr = process.communicate()
        if cancel_token.is_requested():
            raise FFmpegError(CANCELED_ERROR_CODE, CANCELED_MESSAGE)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        cancel_token.clear_process(process)


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
