"""Extract and analyze target frames for suspected black screens."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import subprocess

from framebatch.core.models import BlackFrameStatus
from framebatch.ffmpeg.errors import FFmpegError

_CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0


DEFAULT_AVERAGE_LUMA_THRESHOLD = 16.0
DEFAULT_BRIGHT_PIXEL_RATIO_THRESHOLD = 0.01
DEFAULT_BRIGHT_LUMA_THRESHOLD = 32
DEFAULT_BLACK_FRAME_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class BlackFrameCheckResult:
    status: BlackFrameStatus
    average_luma: float | None
    bright_pixel_ratio: float | None
    message: str


class BlackFrameChecker:
    def __init__(
        self,
        ffmpeg_path: Path | None,
        *,
        timeout_seconds: int = DEFAULT_BLACK_FRAME_TIMEOUT_SECONDS,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.timeout_seconds = timeout_seconds

    def check(self, video_path: Path, frame_zero_based: int) -> BlackFrameCheckResult:
        if self.ffmpeg_path is None:
            raise FFmpegError("FFMPEG_NOT_FOUND", "ffmpeg 不可用，无法检测黑屏帧。")

        command = [
            str(self.ffmpeg_path),
            "-v",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"select=eq(n\\,{frame_zero_based})",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "ppm",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
                creationflags=_CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise FFmpegError(
                "BLACK_FRAME_CHECK_TIMEOUT",
                f"黑屏检测超时，已超过 {self.timeout_seconds} 秒。",
            ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise FFmpegError("BLACK_FRAME_CHECK_FAILED", detail or "黑屏检测抽帧失败。")
        if not completed.stdout:
            raise FFmpegError("FRAME_OUT_OF_RANGE", "未抽取到目标帧，请检查帧号是否超出范围。")

        try:
            return analyze_ppm_bytes(completed.stdout)
        except ValueError as exc:
            raise FFmpegError("BLACK_FRAME_CHECK_FAILED", f"无法解析目标帧图像：{exc}") from exc


def analyze_ppm_bytes(data: bytes) -> BlackFrameCheckResult:
    width, height, max_value, pixel_offset = _parse_ppm_header(data)
    if max_value != 255:
        raise ValueError("Only 8-bit PPM images are supported.")

    expected_size = width * height * 3
    pixels = data[pixel_offset : pixel_offset + expected_size]
    if len(pixels) != expected_size:
        raise ValueError("PPM pixel data is incomplete.")

    total_luma = 0.0
    bright_pixels = 0
    pixel_count = width * height
    for index in range(0, len(pixels), 3):
        red = pixels[index]
        green = pixels[index + 1]
        blue = pixels[index + 2]
        luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        total_luma += luma
        if luma > DEFAULT_BRIGHT_LUMA_THRESHOLD:
            bright_pixels += 1

    average_luma = total_luma / pixel_count
    bright_pixel_ratio = bright_pixels / pixel_count
    suspected = (
        average_luma < DEFAULT_AVERAGE_LUMA_THRESHOLD
        and bright_pixel_ratio < DEFAULT_BRIGHT_PIXEL_RATIO_THRESHOLD
    )

    if suspected:
        return BlackFrameCheckResult(
            status=BlackFrameStatus.SUSPECTED_BLACK,
            average_luma=average_luma,
            bright_pixel_ratio=bright_pixel_ratio,
            message="疑似黑屏帧，建议修改目标帧后再处理。",
        )

    return BlackFrameCheckResult(
        status=BlackFrameStatus.OK,
        average_luma=average_luma,
        bright_pixel_ratio=bright_pixel_ratio,
        message="目标帧亮度正常。",
    )


def _parse_ppm_header(data: bytes) -> tuple[int, int, int, int]:
    tokens: list[bytes] = []
    index = 0
    length = len(data)

    while len(tokens) < 4:
        while index < length and data[index] in b" \t\r\n":
            index += 1
        if index < length and data[index] == ord("#"):
            while index < length and data[index] not in b"\r\n":
                index += 1
            continue
        start = index
        while index < length and data[index] not in b" \t\r\n":
            index += 1
        if start == index:
            raise ValueError("Invalid PPM header.")
        tokens.append(data[start:index])

    if index < length and data[index] in b" \t\r\n":
        index += 1

    magic, raw_width, raw_height, raw_max = tokens
    if magic != b"P6":
        raise ValueError("Only binary P6 PPM images are supported.")
    return int(raw_width), int(raw_height), int(raw_max), index
