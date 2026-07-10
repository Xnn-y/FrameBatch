# FrameBatch

FrameBatch 是一个 Windows 桌面工具，用于给一整部剧集的每个视频前面插入同一张封面图片，并统一输出为 MP4 视频。应用基于 PySide6 和 FFmpeg 构建。

## 当前能力

- 扫描输入目录中的视频、封面图片候选、候选视频和其他文件。
- 自动识别输入目录中的唯一图片作为统一封面；识别不了时也支持手动选择封面。
- 批量把统一封面插入到每个视频的第一帧位置。
- 输出视频统一为 MP4，默认写入输入目录下的 `videos` 文件夹。
- 支持统一命名，批量任务会自动生成 `名称_1.mp4`、`名称_2.mp4`。
- 支持覆盖已有输出，以及处理中途终止。
- 终止、失败、超时时会清理未完成的临时输出文件。
- 生成固定的 `reports/result.csv`，每次处理覆盖最新结果，不堆积 CSV 文件。
- 历史记录保留最近 50 次，支持打开视频目录、双击导出对应 CSV、删除单条或清空全部。

## 开发运行

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m framebatch.main
```

## 打包

安装打包依赖：

```powershell
python -m pip install -e ".[build]"
```

执行 Windows 打包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1 -Clean
```

打包结果位于：

```text
dist/FrameBatch/FrameBatch.exe
```

## FFmpeg

FrameBatch 会按以下顺序查找 FFmpeg：

1. 用户在界面中手动配置的 `ffmpeg.exe`。
2. 发布目录下的内置路径：`tools/ffmpeg/ffmpeg.exe` 或 `tools/ffmpeg/bin/ffmpeg.exe`。
3. 系统 `PATH` 中的 `ffmpeg` 和 `ffprobe`。

如果需要发布内置 FFmpeg 的版本，在打包前放置：

```text
tools/ffmpeg/ffmpeg.exe
tools/ffmpeg/ffprobe.exe
```

PyInstaller onedir 包会自动将它们带入 `dist/FrameBatch/_internal/tools/ffmpeg/`。应用也兼容用户手动放在 `FrameBatch.exe` 同级的 `tools/ffmpeg/`。

更多发布验证步骤见 [docs/RELEASE.md](docs/RELEASE.md)。
