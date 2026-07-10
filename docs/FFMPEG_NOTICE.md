# FFmpeg Notice

FrameBatch uses FFmpeg and ffprobe as external executables for video probing and processing.

This repository does not require a bundled FFmpeg binary. A release package may either:

- ask users to configure their own `ffmpeg.exe`; or
- include `ffmpeg.exe` and `ffprobe.exe` under `tools/ffmpeg/`.

If a release package includes FFmpeg binaries, the publisher must include the license and attribution materials that apply to the chosen FFmpeg build. Different FFmpeg builds can have different licensing obligations depending on how they were configured and distributed.

Recommended release package location:

```text
FrameBatch/
  FrameBatch.exe
  docs/
    FFMPEG_NOTICE.md
  tools/
    ffmpeg/
      ffmpeg.exe
      ffprobe.exe
```
