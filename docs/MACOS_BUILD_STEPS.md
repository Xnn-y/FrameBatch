# FrameBatch macOS 打包操作手册

这份文档用于在一台 Mac 电脑上从 GitHub 拉取 FrameBatch 仓库，并打包出可发给 macOS 用户的 zip。

## 1. 确认 Mac 架构

打开“终端 Terminal”，执行：

```bash
uname -m
```

结果含义：

```text
arm64  = Apple Silicon Mac，也就是 M1/M2/M3/M4，最终生成 macos-arm64 包
x86_64 = Intel Mac，最终生成 macos-x64 包
```

## 2. 检查基础工具

执行：

```bash
xcode-select -p
python3 --version
git --version
```

如果 `xcode-select -p` 没有输出路径，先安装 Apple 命令行工具：

```bash
xcode-select --install
```

如果没有 Homebrew，安装 Homebrew：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装 Python、Git 和 FFmpeg：

```bash
brew install python git ffmpeg
```

确认 FFmpeg 可用：

```bash
ffmpeg -version
ffprobe -version
which ffmpeg
which ffprobe
```

Apple Silicon Mac 常见路径是：

```text
/opt/homebrew/bin/ffmpeg
/opt/homebrew/bin/ffprobe
```

Intel Mac 常见路径是：

```text
/usr/local/bin/ffmpeg
/usr/local/bin/ffprobe
```

## 3. 用 VS Code 拉取项目代码

如果 Mac 上已经安装 VS Code，推荐直接从 VS Code 里 clone 仓库。

1. 打开 VS Code。
2. 按 `Command + Shift + P`。
3. 输入：

```text
Git: Clone
```

4. 选择 `Git: Clone`。
5. 粘贴仓库地址：

```text
https://github.com/Xnn-y/FrameBatch.git
```

6. 选择保存位置，例如：

```text
Desktop
```

7. 等待 VS Code clone 完成。
8. VS Code 提示 `Would you like to open the cloned repository?` 时，点击 `Open`。

打开后，左侧文件列表应该能看到：

```text
FrameBatch.spec
README.md
framebatch
scripts
docs
```

如果已经 clone 过：

1. 打开 VS Code。
2. 点击 `File -> Open Folder...`。
3. 选择已经存在的 `FrameBatch` 文件夹。
4. 打开后，在左侧源代码管理面板或内置终端里更新代码。

使用 VS Code 内置终端更新代码：

```bash
git pull
```

确认仓库里有 macOS 打包脚本：

```bash
ls scripts/build_macos.sh
```

如果提示找不到文件，说明 GitHub 上还不是最新代码，需要先在 Windows 端提交并推送 macOS 适配改动。

## 3.1 打开 VS Code 内置终端

打开项目后，在 VS Code 里打开内置终端：

```text
Terminal -> New Terminal
```

或使用快捷键：

```text
Control + `
```

后面所有命令都可以在 VS Code 下方的内置终端里执行。确认终端当前位置是项目根目录：

```bash
pwd
ls
```

你应该能看到：

```text
FrameBatch.spec
README.md
framebatch
scripts
docs
```

## 4. 创建 Python 虚拟环境

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,build]"
```

如果 VS Code 弹出 Python 解释器选择，选择项目里的虚拟环境：

```text
.venv/bin/python
```

也可以手动选择：

1. 按 `Command + Shift + P`。
2. 输入 `Python: Select Interpreter`。
3. 选择 `./.venv/bin/python`。

确认 PyInstaller 可用：

```bash
python -m PyInstaller --version
```

## 5. 跑测试

```bash
python -m pytest
```

理想结果类似：

```text
59 passed
```

如果测试失败，先不要打包，把终端里的报错保存下来。

## 6. 源码方式启动验证

先用源码启动一次，确认 GUI 和 FFmpeg 检测正常：

```bash
python -m framebatch.main
```

打开后检查：

1. 窗口能正常显示。
2. FFmpeg 状态能显示可用。
3. 如果 FFmpeg 不可用，在界面中手动选择 `which ffmpeg` 显示的路径。

关闭应用后继续下一步。

## 7. 准备一个小测试目录

在桌面建一个测试目录：

```bash
mkdir -p ~/Desktop/framebatch-test
```

放入：

```text
一个短视频，例如 test.mp4
一张封面图，例如 cover.jpg
```

再次运行：

```bash
python -m framebatch.main
```

在界面里：

1. 选择 `~/Desktop/framebatch-test` 作为输入目录。
2. 点击扫描。
3. 确认能识别视频和封面图。
4. 点击开始处理。
5. 确认生成 MP4 输出。

这一步通过后，再做正式打包。

## 8. 正式打包

回到项目根目录，确保虚拟环境已激活：

```bash
source .venv/bin/activate
bash scripts/build_macos.sh --clean
```

成功后会看到类似：

```text
Build completed successfully
Distributable : /Users/.../FrameBatch/dist/FrameBatch-v0.1.0-macos-arm64.zip
```

Apple Silicon Mac 产物：

```text
dist/FrameBatch-v0.1.0-macos-arm64.zip
```

Intel Mac 产物：

```text
dist/FrameBatch-v0.1.0-macos-x64.zip
```

## 9. 验证打包后的 app

Apple Silicon Mac：

```bash
open dist/FrameBatch-v0.1.0-macos-arm64/FrameBatch.app
```

Intel Mac：

```bash
open dist/FrameBatch-v0.1.0-macos-x64/FrameBatch.app
```

如果 macOS 提示“无法打开，因为无法验证开发者”，这是未签名 app 的常见提示。测试阶段可以执行：

Apple Silicon Mac：

```bash
xattr -dr com.apple.quarantine dist/FrameBatch-v0.1.0-macos-arm64/FrameBatch.app
open dist/FrameBatch-v0.1.0-macos-arm64/FrameBatch.app
```

Intel Mac：

```bash
xattr -dr com.apple.quarantine dist/FrameBatch-v0.1.0-macos-x64/FrameBatch.app
open dist/FrameBatch-v0.1.0-macos-x64/FrameBatch.app
```

## 10. 发给用户的文件

只需要发送最终 zip。

Apple Silicon Mac 用户：

```text
dist/FrameBatch-v0.1.0-macos-arm64.zip
```

Intel Mac 用户：

```text
dist/FrameBatch-v0.1.0-macos-x64.zip
```

不要只发送 `FrameBatch.app` 里面的单个可执行文件。

## 11. 给用户的简短说明

可以随 zip 一起发这段：

```text
请下载对应芯片版本：
- M1/M2/M3/M4 Mac：FrameBatch-v0.1.0-macos-arm64.zip
- Intel Mac：FrameBatch-v0.1.0-macos-x64.zip

解压后打开 FrameBatch.app。
如果系统提示无法验证开发者，请到 系统设置 -> 隐私与安全性 -> 仍要打开。

如果应用提示 FFmpeg 不可用，请先安装 FFmpeg：
brew install ffmpeg
```

## 12. 常见问题

### 找不到 `scripts/build_macos.sh`

说明 Mac 上拉到的仓库不是最新代码。先在 Windows 端提交并推送 macOS 适配改动，然后 Mac 上执行：

```bash
git pull
```

### `brew` 命令不存在

说明还没有安装 Homebrew。先执行本文第 2 步里的 Homebrew 安装命令。

### `python -m pytest` 失败

不要继续打包。先保存终端报错，再排查依赖或代码问题。

### app 打开后提示 FFmpeg 不可用

执行：

```bash
which ffmpeg
which ffprobe
```

然后在应用界面里手动选择 `which ffmpeg` 输出的路径。

### 用户反馈打不开 app

未签名 app 可能被 Gatekeeper 拦截。测试阶段可以让用户在“系统设置 -> 隐私与安全性”里选择“仍要打开”。公开发布建议后续做 Developer ID 签名和 notarization。
