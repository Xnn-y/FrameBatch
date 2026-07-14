# FrameBatch 发布说明

## 发布目录

Windows 打包后生成：

```text
dist/
  FrameBatch/
    FrameBatch.exe
    docs/
      FFMPEG_NOTICE.md
      RELEASE.md
    _internal/
      docs/
      tools/
        ffmpeg/
          ffmpeg.exe      可选
          ffprobe.exe     可选
    tools/
      ffmpeg/             可选，用户也可以手动放在 exe 同级
```

`tools/ffmpeg` 是可选目录。若打包前仓库中存在 Windows 的 `tools/ffmpeg/ffmpeg.exe` / `tools/ffmpeg/ffprobe.exe`，或 macOS 的 `tools/ffmpeg/ffmpeg` / `tools/ffmpeg/ffprobe`，PyInstaller 会自动把它们复制到发布目录的 `_internal/tools/ffmpeg/`。应用同时兼容用户手动放在 `FrameBatch.exe`、`FrameBatch.app` 同级或系统 PATH 中的 FFmpeg。

macOS 打包后生成：

```text
dist/
  FrameBatch-v0.1.0-macos-arm64/
    FrameBatch.app
    docs/
      FFMPEG_NOTICE.md
      RELEASE.md
      MACOS_ADAPTATION_PLAN.md
  FrameBatch-v0.1.0-macos-arm64.zip   Apple Silicon Mac
  FrameBatch-v0.1.0-macos-x64.zip     Intel Mac
```

macOS 内置 FFmpeg 时使用无扩展名文件：`tools/ffmpeg/ffmpeg` 和 `tools/ffmpeg/ffprobe`。应用也兼容用户手动配置 Homebrew 等方式安装的本机 FFmpeg。

## 打包命令

```powershell
python -m pip install -e ".[build]"
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1 -Clean
```

macOS：

```bash
python3 -m pip install -e ".[build]"
bash scripts/build_macos.sh --clean
```

首次在 Mac 上配置环境和打包，请按 `docs/MACOS_BUILD_STEPS.md` 的完整步骤执行。

构建成功后运行：

```powershell
dist/FrameBatch/FrameBatch.exe
```

macOS 构建成功后运行：

```bash
open dist/FrameBatch-v0.1.0-macos-arm64/FrameBatch.app
```

## 手工验证清单

1. 在开发机运行 `dist/FrameBatch/FrameBatch.exe`，确认窗口能启动。
2. 不放置 FFmpeg 时启动，确认界面显示 FFmpeg 不可用，并能手动选择 `ffmpeg` 或 `ffmpeg.exe`。
3. 设置内置 FFmpeg 后重新打包，确认启动后显示正在使用内置 FFmpeg。
4. 准备一个输入目录，只放入一整部剧集视频和一张统一封面图片。
5. 扫描输入目录，确认文件分类正确，并自动识别出唯一封面图片。
6. 在同一目录放入第二张图片后重新扫描，确认不会自动填入封面；手动选择一张封面后可以继续处理。
7. 执行一次处理任务，确认每个视频输出为 MP4。
8. 检查输出视频第一帧，确认显示自动识别到的封面图片，后续内容为原视频内容。
9. 点击终止处理，确认当前任务被取消，后续任务不继续执行，未完成的临时输出文件被清理。
10. 打开历史记录，确认完成时间显示为北京时间。
11. 双击历史记录，确认会打开对应 CSV。
12. 点击历史记录中的垃圾桶图标，确认只删除该条历史，不删除输出视频。
13. 点击清空历史，确认历史记录清空，输出视频文件仍保留。
14. 将发布目录复制到没有项目源码的机器上，重复启动、配置 FFmpeg、扫描、处理验证。
15. macOS 上确认 `FrameBatch.app` 能启动，并能识别 `tools/ffmpeg/ffmpeg` 或系统 PATH 中的 `ffmpeg`。

## 发布注意事项

- `reports/result.csv` 是应用运行时生成的最新结果文件，每次处理会覆盖，不应提交到 Git。
- 用户配置和历史记录在 Windows 默认写入 `%APPDATA%/FrameBatch/`，在 macOS 默认写入用户主目录下的 `.framebatch` 回退路径。
- 如果发布包内置 FFmpeg，请同时检查并随包提供所选 FFmpeg 构建对应的许可证说明。
- 第一版发布包可以不内置 FFmpeg，让用户在界面中配置本机 `ffmpeg` / `ffmpeg.exe`。
