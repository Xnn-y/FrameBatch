# FrameBatch macOS 适配计划

## 目标

让 FrameBatch 保持一套源码，同时发布独立的 Windows 和 macOS 安装包。

## 发布形态

- Windows: `FrameBatch-vX.Y.Z-windows-x64.zip`
- Apple Silicon Mac: `FrameBatch-vX.Y.Z-macos-arm64.zip`
- Intel Mac: `FrameBatch-vX.Y.Z-macos-x64.zip`
- 如果后续做 universal2: `FrameBatch-vX.Y.Z-macos-universal2.zip`

## 开发计划

1. 运行期跨平台
   - FFmpeg 定位同时支持 `ffmpeg` / `ffprobe` 和 `ffmpeg.exe` / `ffprobe.exe`。
   - 用户可以选择 FFmpeg 可执行文件，也可以选择所在目录。
   - UI 文案避免只提示 `ffmpeg.exe`。

2. 打包期跨平台
   - PyInstaller spec 同时收集 Windows 和 macOS 命名的 FFmpeg 二进制。
   - macOS 构建时生成 `FrameBatch.app`。
   - macOS 构建脚本输出带平台架构后缀的 zip。

3. 文档和交付
   - README 说明 Windows 与 macOS 分别如何构建。
   - FFmpeg notice 同时说明两类平台的二进制命名。
   - 发布包命名清楚区分平台和 CPU 架构。

## Windows 可验证项

- `python -m pytest` 全量测试通过。
- Windows 的 `ffmpeg.exe` 定位逻辑不回退。
- 通过 monkeypatch 模拟 macOS 的 `ffmpeg` / `ffprobe` 路径定位。
- PyInstaller spec 在 Windows 上仍保留 Windows onedir 构建路径。

## 必须在 macOS 实机验证项

- `python -m framebatch.main` 能启动 GUI。
- `python -m PyInstaller --noconfirm FrameBatch.spec` 能生成 `FrameBatch.app`。
- `scripts/build_macos.sh --clean` 能生成 `FrameBatch-vX.Y.Z-macos-*.zip`。
- 内置或手动配置的 `ffmpeg` / `ffprobe` 能被检测到。
- 用一个包含视频和封面图的目录完成扫描与处理。
- 首次打开时如被 Gatekeeper 拦截，确认用户提示或签名方案。

## 后续增强

- 增加 macOS 图标和 app metadata。
- 做 Apple Developer ID 签名与 notarization。
- 需要同时覆盖 Intel 和 Apple Silicon 时，提供双架构包或 universal2 包。
