# FFmpeg Notice

FrameBatch uses FFmpeg and ffprobe as external executables for video probing and processing.

This repository does not require a bundled FFmpeg binary. A release package may either:

- ask users to configure their own `ffmpeg` / `ffmpeg.exe`; or
- include `ffmpeg` and `ffprobe` under `tools/ffmpeg/`.

If a release package includes FFmpeg binaries, the publisher must include the license and attribution materials that apply to the chosen FFmpeg build. Different FFmpeg builds can have different licensing obligations depending on how they were configured and distributed.

Recommended release package location:

```text
FrameBatch/
  FrameBatch.exe or FrameBatch
  docs/
    FFMPEG_NOTICE.md
  tools/
    ffmpeg/
      ffmpeg      # macOS / Linux
      ffprobe     # macOS / Linux
      ffmpeg.exe  # Windows
      ffprobe.exe # Windows
```
