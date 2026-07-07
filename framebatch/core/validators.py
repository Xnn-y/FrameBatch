"""Validation helpers for core workflow input."""

from __future__ import annotations

from pathlib import Path


def validate_frame_user_index(value: int) -> int:
    if not isinstance(value, int):
        raise TypeError("Frame index must be an integer.")
    if value < 1:
        raise ValueError("Frame index must be greater than or equal to 1.")
    return value


def ensure_directory(path: str | Path, *, must_exist: bool) -> Path:
    resolved = Path(path)
    if must_exist and not resolved.is_dir():
        raise FileNotFoundError(f"Directory does not exist: {resolved}")
    return resolved
