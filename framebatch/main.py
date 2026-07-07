"""Command-line entry point for FrameBatch."""

from __future__ import annotations

import sys

from framebatch.app import run


def main() -> int:
    try:
        return run()
    except RuntimeError as exc:
        print(f"FrameBatch failed to start: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
