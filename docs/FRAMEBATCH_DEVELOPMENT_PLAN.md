# FrameBatch 批量封面抽帧工具开发计划

## 1. 项目目标

FrameBatch 是一个基于 FFmpeg 的 Windows 桌面工具，用于批量处理目录中的视频文件。用户选择一个输入目录后，工具扫描目录内容，将文件分为视频文件和非视频文件；用户为视频任务配置目标帧号后，工具逐个执行任务，并为每个成功任务输出两类产物：

1. 封面图：从目标视频中精确抽取指定帧。
2. 去帧视频：删除该目标帧后重新编码输出为 MP4。

工具需要在界面中清晰展示每个任务的执行状态、成功产物、失败原因，并在输出目录生成 `result.json` 和 `result.csv`，同时维护全局历史记录，便于查询曾经处理过的目录和任务结果。

## 2. 第一版范围

### 2.1 必须支持

- 桌面 GUI 应用。
- 用户选择输入目录。
- 用户选择输出目录。
- 默认输出目录为输入目录下的 `covers`。
- 记住上一次用户选择的输出目录。
- 扫描输入目录中的一级文件。
- 识别视频文件和非视频文件。
- 视频文件进入任务列表，非视频文件只展示统计信息或明细，不创建处理任务。
- 所有视频默认使用同一个目标帧号。
- 每个视频允许单独修改目标帧号。
- 检测目标帧是否疑似黑屏帧。
- 对疑似黑屏帧给出明确提示。
- 用户可在提示后修改该视频的目标帧号。
- 每个视频成功后输出一张封面图。
- 每个视频成功后输出一个删除目标帧后的 MP4 视频。
- 任务按队列逐个执行。
- 每个任务展示状态、进度、输出路径或失败原因。
- 任务结束后生成 `result.json`。
- 任务结束后生成 `result.csv`。
- 维护全局历史 `history.json`。
- 启动时检测 FFmpeg / ffprobe。
- 支持外部 FFmpeg 路径配置。
- 架构预留内置 FFmpeg 发布方式。

### 2.2 第一版暂不支持

- 递归扫描子目录。
- 多帧抽取。
- 按时间点抽帧。
- 按百分比抽帧。
- 不重新编码删除单帧。
- 多任务并行处理。
- 视频预览时间轴。
- 自动云端更新 FFmpeg。

这些能力可作为后续版本扩展，不进入第一版主流程，避免核心逻辑过早复杂化。

## 3. 技术选型

### 3.1 推荐方案

- 语言：Python 3.11+
- GUI：PySide6
- 视频处理：FFmpeg + ffprobe
- 打包：PyInstaller
- 配置与历史：JSON
- 结果表格：CSV
- 测试：pytest

### 3.2 选择理由

PySide6 适合构建长期维护的桌面 GUI，支持表格、进度条、后台线程、文件选择、菜单、设置页等能力。FFmpeg 是视频处理的核心执行器，Python 负责流程编排、参数校验、任务状态管理和用户界面。

### 3.3 FFmpeg 发布策略

开发阶段采用“检测本机 FFmpeg + 手动配置路径”的方式：

1. 优先查找应用目录内的 `tools/ffmpeg/bin/ffmpeg.exe` 与 `ffprobe.exe`。
2. 如果不存在，检测系统 `PATH`。
3. 如果仍不存在，允许用户在设置界面选择 `ffmpeg.exe`。
4. 根据 `ffmpeg.exe` 所在目录推断 `ffprobe.exe`。
5. 如果二者不完整，禁止启动任务，并提示用户配置。

发布阶段可选择是否内置 FFmpeg：

- 内置优点：开箱即用，用户不需要额外安装。
- 内置成本：安装包体积增加，需要确认 FFmpeg 构建版本和许可说明。
- 推荐实现：代码层面始终支持内置路径，但第一轮开发不强制打包 FFmpeg。

## 4. 核心业务规则

### 4.1 文件识别规则

文件识别分两步：

1. 扩展名初筛。
2. ffprobe 精确确认。

常见视频扩展名：

```text
.mp4
.mov
.mkv
.avi
.flv
.wmv
.webm
.m4v
.ts
.mts
.m2ts
```

扩展名命中的文件不直接视为有效视频，必须通过 ffprobe 检测到视频流后才进入视频任务列表。

非视频文件分为两类：

- 扩展名不在视频候选列表中。
- 扩展名像视频，但 ffprobe 未检测到有效视频流或文件损坏。

第二类文件需要在扫描结果中说明原因。

### 4.2 帧号规则

用户界面使用从 1 开始的帧号，符合普通用户直觉：

```text
用户输入第 1 帧 -> FFmpeg 内部 n=0
用户输入第 N 帧 -> FFmpeg 内部 n=N-1
```

内部执行层统一使用从 0 开始的 `frame_index_zero_based`，避免与 FFmpeg 的 `select` 表达式混淆。

任务创建前必须校验：

- 帧号必须为正整数。
- 如果已获取总帧数，帧号不能大于总帧数。
- 如果总帧数未知，允许创建任务，但执行阶段需要处理越界失败。

### 4.3 黑屏帧检测规则

目标帧检测分为“疑似黑屏提示”，不自动阻止任务执行。

检测流程：

1. 使用 FFmpeg 抽取目标帧到临时图片。
2. 分析图片亮度。
3. 如果平均亮度低于阈值，且高亮像素比例低于阈值，则标记为疑似黑屏。
4. 在任务表中显示警告。
5. 用户可以保持原帧号继续执行，也可以单独修改该视频帧号。

推荐默认阈值：

```text
平均亮度阈值：16 / 255
高亮像素阈值：小于 1% 像素亮度超过 32 / 255
```

黑屏检测只能判断“疑似黑屏”，不能承诺识别所有无效封面。例如纯黑转场、夜景、字幕黑底、片头黑屏都可能触发提示。因此界面文案应使用“疑似黑屏”，避免写成“黑屏错误”。

### 4.4 抽封面规则

每个视频输出一张封面图，默认使用 JPG：

```text
{原文件名}_frame_{用户帧号}.jpg
```

示例：

```text
input:  episode01.mp4
frame: 25
cover:  episode01_frame_25.jpg
```

后续可扩展 PNG/WebP，但第一版默认 JPG 足够。

### 4.5 删除目标帧规则

用户已接受重新编码。第一版采用精确删除指定单帧的模式：

- 输出格式统一为 MP4。
- 视频流重新编码。
- 音频流尽量复制。
- 删除目标帧后重建视频时间戳。

推荐 FFmpeg 过滤思路：

```text
select='not(eq(n\,FRAME_INDEX_ZERO_BASED))',setpts=N/FRAME_RATE/TB
```

如果原视频没有音频：

```text
仅输出视频流
```

如果原视频有音频：

```text
视频重新编码，音频 copy
```

若音频 copy 因容器或编码兼容性失败，可降级为音频重新编码 AAC，并在结果中记录降级信息。

### 4.6 输出命名规则

第一版支持三种命名策略，默认使用原文件名派生命名：

1. 沿用原文件名派生，默认推荐。
2. 统一前缀命名。
3. 单个任务自定义命名。

默认规则：

```text
封面图：{stem}_frame_{frame}.jpg
去帧视频：{stem}_removed_frame_{frame}.mp4
```

示例：

```text
输入文件：D:/videos/a.mp4
目标帧：25
输出目录：D:/videos/covers

封面图：D:/videos/covers/a_frame_25.jpg
去帧视频：D:/videos/covers/a_removed_frame_25.mp4
```

命名冲突处理：

- 默认不覆盖已有文件。
- 如果目标文件已存在，任务进入“等待用户处理”或执行前提示。
- 后续可提供“覆盖已有文件”选项。
- 第一版建议提供全局复选框：允许覆盖已有输出。

## 5. 用户流程

### 5.1 首次启动

1. 应用加载 `settings.json`。
2. 检测 FFmpeg 和 ffprobe。
3. 加载 `history.json`。
4. 如果 FFmpeg 不可用，在顶部显示错误状态，并引导用户配置路径。
5. 如果 FFmpeg 可用，允许用户选择输入目录。

### 5.2 创建任务

1. 用户选择输入目录。
2. 系统默认输出目录为 `{输入目录}/covers`。
3. 如果用户曾经选择过输出目录，则优先显示上一次输出目录。
4. 界面提供“使用默认输出目录”按钮，避免用户换目录后误用旧输出目录。
5. 用户输入全局默认帧号。
6. 系统扫描目录。
7. 系统展示视频数量、非视频数量、异常候选数量。
8. 视频文件进入任务表。
9. 每个任务继承全局默认帧号。
10. 系统可对目标帧执行黑屏检测。
11. 疑似黑屏任务显示警告。
12. 用户可单独修改任务帧号。
13. 用户点击开始处理。

### 5.3 执行任务

1. 系统创建本次运行记录 `run_id`。
2. 系统确保输出目录存在。
3. 系统逐个执行任务。
4. 每个任务先抽封面。
5. 封面成功后再生成去帧视频。
6. 两个产物都成功，任务才算成功。
7. 任一产物失败，任务标记失败，并记录失败阶段。
8. 单个任务失败不影响后续任务。
9. 全部任务结束后写入 `result.json` 和 `result.csv`。
10. 更新全局 `history.json`。

### 5.4 查看结果

任务表中每行显示：

- 文件名
- 原始路径
- 时长
- 帧率
- 总帧数
- 目标帧号
- 黑屏检测状态
- 任务状态
- 封面输出路径
- 去帧视频输出路径
- 失败原因

底部汇总显示：

- 总任务数
- 成功数
- 失败数
- 跳过数
- 输出目录
- result.json 路径
- result.csv 路径

## 6. 界面设计规划

### 6.1 主界面区域

主界面分为五个区域：

1. 顶部路径栏。
2. FFmpeg 状态栏。
3. 扫描统计区。
4. 任务表格。
5. 执行结果与日志区。

### 6.2 顶部路径栏

包含：

- 输入目录选择框。
- 输出目录选择框。
- 使用默认输出目录按钮。
- 扫描按钮。
- 全局默认帧号输入框。

### 6.3 FFmpeg 状态栏

展示：

- FFmpeg 可用状态。
- ffprobe 可用状态。
- 当前 FFmpeg 路径。
- 设置入口。

状态示例：

```text
FFmpeg 可用：D:/tools/ffmpeg/bin/ffmpeg.exe
FFmpeg 不可用：请在设置中配置 ffmpeg.exe
```

### 6.4 任务表格

字段：

```text
选择
文件名
时长
帧率
总帧数
目标帧
黑屏检测
状态
封面
去帧视频
消息
```

交互：

- 目标帧列可编辑。
- 可批量应用全局帧号。
- 疑似黑屏以警告状态显示。
- 成功后可打开输出文件所在位置。
- 失败后可查看详细错误。

### 6.5 历史页

历史页读取全局 `history.json`，展示最近运行记录：

```text
运行时间
输入目录
输出目录
任务总数
成功数
失败数
result.json
result.csv
```

支持：

- 打开输出目录。
- 打开 result.json。
- 打开 result.csv。
- 根据历史记录重新加载输入目录和输出目录。

## 7. 代码架构规范

### 7.1 分层原则

代码必须按职责分层，GUI 不直接拼接 FFmpeg 命令，FFmpeg 执行层不依赖 GUI 控件。

推荐目录结构：

```text
framebatch/
  app.py
  main.py
  config/
    settings.py
    history.py
  core/
    models.py
    scanner.py
    task_queue.py
    validators.py
    naming.py
    result_writer.py
  ffmpeg/
    locator.py
    probe.py
    commands.py
    runner.py
    errors.py
    black_frame.py
  ui/
    main_window.py
    task_table.py
    settings_dialog.py
    history_view.py
    workers.py
  tests/
    test_scanner.py
    test_naming.py
    test_validators.py
    test_result_writer.py
    test_ffmpeg_errors.py
```

### 7.2 模块职责

`config/settings.py`

- 读取和写入用户设置。
- 保存上一次输入目录。
- 保存上一次输出目录。
- 保存 FFmpeg 路径。
- 保存默认帧号。
- 保存是否覆盖输出。

`config/history.py`

- 维护全局历史记录。
- 按 `run_id` 追加运行摘要。
- 支持按输入目录查询历史。

`core/models.py`

- 定义核心数据结构。
- 不依赖 PySide6。
- 不直接调用 FFmpeg。

建议模型：

```text
VideoFile
NonVideoFile
TaskConfig
FrameTask
TaskResult
RunSummary
```

`core/scanner.py`

- 扫描输入目录。
- 使用扩展名初筛。
- 调用 `ffmpeg/probe.py` 确认视频流。
- 输出视频文件列表和非视频文件列表。

`core/task_queue.py`

- 创建任务队列。
- 管理任务状态。
- 保证任务逐个执行。
- 单任务失败后继续执行后续任务。

`core/validators.py`

- 校验输入目录。
- 校验输出目录。
- 校验帧号。
- 校验输出命名冲突。

`core/naming.py`

- 根据命名策略生成封面路径和去帧视频路径。
- 处理非法文件名字符。
- 处理重名策略。

`core/result_writer.py`

- 写入 `result.json`。
- 写入 `result.csv`。
- 保证字段稳定。

`ffmpeg/locator.py`

- 查找内置 FFmpeg。
- 查找系统 PATH。
- 校验用户配置路径。

`ffmpeg/probe.py`

- 调用 ffprobe。
- 获取视频流信息。
- 获取时长、帧率、总帧数、编码格式、是否有音频。

`ffmpeg/commands.py`

- 只负责构造 FFmpeg 命令参数数组。
- 不执行命令。
- 禁止返回 shell 字符串，避免路径空格和转义问题。

`ffmpeg/runner.py`

- 使用 `subprocess` 执行命令。
- 捕获 stdout、stderr、退出码。
- 支持进度回调。
- 支持取消任务。

`ffmpeg/errors.py`

- 将 FFmpeg 错误转换为用户可读错误。
- 维护错误码。

`ffmpeg/black_frame.py`

- 抽取临时帧图。
- 分析亮度。
- 返回黑屏检测结果。

`ui/workers.py`

- 使用 QThread 或 QRunnable 执行扫描和处理。
- 避免阻塞 GUI 主线程。
- 通过信号向界面报告进度。

### 7.3 数据模型规范

所有核心模型使用 dataclass 或 Pydantic。第一版建议 dataclass，减少依赖。

任务状态枚举：

```text
PENDING
SCANNING
READY
WARNING
RUNNING
SUCCESS
FAILED
CANCELED
SKIPPED
```

黑屏检测状态：

```text
NOT_CHECKED
CHECKING
OK
SUSPECTED_BLACK
FAILED
```

错误码示例：

```text
FFMPEG_NOT_FOUND
FFPROBE_NOT_FOUND
INPUT_DIR_NOT_FOUND
OUTPUT_DIR_NOT_WRITABLE
NO_VIDEO_STREAM
INVALID_FRAME_INDEX
FRAME_OUT_OF_RANGE
OUTPUT_EXISTS
COVER_EXTRACT_FAILED
VIDEO_RENDER_FAILED
AUDIO_COPY_FAILED
BLACK_FRAME_CHECK_FAILED
TASK_CANCELED
UNKNOWN_ERROR
```

### 7.4 命令执行规范

FFmpeg 命令必须使用参数数组，不使用 shell 字符串：

```text
["ffmpeg", "-i", input_path, ...]
```

原因：

- 路径中可能包含空格。
- 路径中可能包含中文。
- Windows shell 转义容易出错。
- 参数数组更适合测试。

执行层必须记录：

- 命令参数。
- 开始时间。
- 结束时间。
- 退出码。
- stderr 摘要。

但 `result.csv` 中不写完整命令，避免过长；完整命令可写入 `result.json` 的 debug 字段，后续可由设置开关控制。

### 7.5 GUI 线程规范

- GUI 主线程只负责界面渲染和用户输入。
- 扫描目录、ffprobe、FFmpeg 处理必须在后台线程执行。
- 后台线程不得直接修改 UI 控件。
- 后台线程通过 signal/slot 上报状态。
- 用户点击取消时，执行层需要终止当前 FFmpeg 子进程，并将剩余任务标记为取消或等待。

### 7.6 错误处理规范

错误处理必须满足：

- 每个失败任务都有明确 `error_code`。
- 每个失败任务都有用户可读 `message`。
- 原始 stderr 可保存在 `debug.stderr_tail`。
- 单任务失败不影响队列继续。
- 扫描失败、配置失败、FFmpeg 不可用属于运行前错误，阻止开始任务。

错误消息示例：

```text
目标帧超出视频总帧数：当前视频约 120 帧，用户选择第 300 帧。
无法写入输出目录：请检查目录权限或选择其他输出目录。
FFmpeg 执行失败：视频编码失败，请查看 result.json 中的调试信息。
```

## 8. FFmpeg 策略

### 8.1 ffprobe 获取视频信息

需要获取：

- 是否存在视频流。
- 视频编码。
- 宽高。
- 时长。
- 帧率。
- 总帧数。
- 是否存在音频流。
- 音频编码。

总帧数优先级：

1. `nb_frames`
2. `duration * avg_frame_rate`
3. 未知

如果总帧数未知，界面显示“未知”，但不阻塞任务创建。

### 8.2 抽取封面

逻辑要求：

- 使用用户输入帧号转换后的 zero-based index。
- 只输出一张图片。
- 输出失败时任务失败，不继续生成去帧视频。

### 8.3 生成去帧视频

逻辑要求：

- 精确删除目标帧。
- 输出 MP4。
- 视频重新编码。
- 默认使用 H.264。
- 默认质量参数建议 CRF 18 或 CRF 20。
- 默认 preset 使用 `medium` 或 `fast`。
- 音频优先 copy。
- 如果音频 copy 失败，可降级 AAC 重试。

重试策略：

1. 第一次：视频 H.264 重编码，音频 copy。
2. 如果失败且错误疑似音频/容器兼容问题：视频 H.264 重编码，音频 AAC。
3. 如果仍失败：任务失败。

### 8.4 进度估算

FFmpeg 可通过 `-progress pipe:1` 输出进度。第一版可实现基础进度：

- 当前任务状态。
- 当前任务耗时。
- 已完成任务数 / 总任务数。
- 总体进度百分比按任务数量估算。

精确的视频编码进度可作为增强项。

## 9. 输出与历史设计

### 9.1 输出目录结构

默认：

```text
input_dir/
  covers/
    video_a_frame_25.jpg
    video_a_removed_frame_25.mp4
    video_b_frame_25.jpg
    video_b_removed_frame_25.mp4
    result.json
    result.csv
```

### 9.2 result.json

`result.json` 是完整机器可读记录，用于恢复和查询细节。

建议结构：

```json
{
  "schema_version": 1,
  "run_id": "20260707_160000_001",
  "app_version": "0.1.0",
  "source_dir": "D:/videos/input",
  "output_dir": "D:/videos/input/covers",
  "started_at": "2026-07-07T16:00:00+08:00",
  "finished_at": "2026-07-07T16:30:00+08:00",
  "default_frame": 25,
  "summary": {
    "total_files": 20,
    "video_count": 12,
    "non_video_count": 8,
    "task_count": 12,
    "success_count": 10,
    "failed_count": 2,
    "canceled_count": 0
  },
  "tasks": [
    {
      "task_id": "task_001",
      "source_video": "D:/videos/input/a.mp4",
      "frame_user_index": 25,
      "frame_zero_based": 24,
      "status": "success",
      "black_frame_status": "OK",
      "cover_path": "D:/videos/input/covers/a_frame_25.jpg",
      "video_path": "D:/videos/input/covers/a_removed_frame_25.mp4",
      "duration_ms": 15000,
      "message": "处理成功"
    }
  ],
  "non_video_files": [
    {
      "path": "D:/videos/input/readme.txt",
      "reason": "扩展名不是视频候选格式"
    }
  ]
}
```

### 9.3 result.csv

`result.csv` 面向用户用 Excel 查看。

字段：

```text
status,source_video,frame_user_index,black_frame_status,cover_path,video_path,error_code,message,duration_ms
```

CSV 只记录任务级结果，不记录完整非视频文件列表，避免表格过宽。非视频统计保留在 `result.json`。

### 9.4 history.json

全局历史用于界面查询，不替代每次运行的 `result.json`。

建议路径：

```text
%APPDATA%/FrameBatch/history.json
```

建议结构：

```json
{
  "schema_version": 1,
  "runs": [
    {
      "run_id": "20260707_160000_001",
      "source_dir": "D:/videos/input",
      "output_dir": "D:/videos/input/covers",
      "started_at": "2026-07-07T16:00:00+08:00",
      "finished_at": "2026-07-07T16:30:00+08:00",
      "task_count": 12,
      "success_count": 10,
      "failed_count": 2,
      "result_json": "D:/videos/input/covers/result.json",
      "result_csv": "D:/videos/input/covers/result.csv"
    }
  ]
}
```

历史策略：

- 每次运行结束后追加一条摘要。
- 如果 `result.json` 被移动或删除，历史页显示“结果文件不存在”。
- 历史列表默认按时间倒序。
- 可限制最多保留 500 条记录。
- 不将完整任务明细重复写入 history，避免文件越来越大。

## 10. 阶段开发计划

### 阶段 0：项目骨架与基础规范

目标：

- 建立 Python 项目结构。
- 明确模块边界。
- 接入格式化、测试和基础配置。

交付物：

- 项目目录结构。
- 应用入口。
- 基础配置读写。
- pytest 基础测试。

验证步骤：

1. 运行单元测试，确认测试框架可用。
2. 启动空白 GUI，确认窗口正常显示。
3. 修改配置后重启应用，确认配置能持久化。

验收标准：

- GUI 可启动。
- 配置文件能读写。
- 测试命令能成功执行。

### 阶段 1：FFmpeg 定位与视频扫描

目标：

- 检测 FFmpeg / ffprobe。
- 扫描输入目录。
- 区分视频文件与非视频文件。

交付物：

- FFmpeg 路径检测模块。
- ffprobe 视频信息读取模块。
- 文件扫描模块。
- 扫描结果界面展示。

验证步骤：

1. 在系统 PATH 存在 FFmpeg 时启动应用，确认状态显示可用。
2. 手动配置 FFmpeg 路径，确认应用保存并复用。
3. 选择包含视频、图片、文本、伪视频文件的目录。
4. 确认有效视频进入任务列表。
5. 确认非视频文件不创建任务。
6. 确认损坏视频或伪视频显示合理原因。

验收标准：

- 可准确识别有效视频。
- 非视频不会进入任务队列。
- FFmpeg 不可用时不能开始任务，并显示清晰提示。

### 阶段 2：任务配置与黑屏检测

目标：

- 支持全局默认帧号。
- 支持单任务修改帧号。
- 支持目标帧疑似黑屏检测。

交付物：

- 帧号校验。
- 任务模型。
- 黑屏检测模块。
- 任务表可编辑目标帧。
- 黑屏警告展示。

验证步骤：

1. 输入全局帧号 25，扫描后确认所有任务继承第 25 帧。
2. 单独修改一个视频为第 50 帧，确认只影响该任务。
3. 输入 0、负数、非数字，确认界面拒绝。
4. 对已知黑屏帧执行检测，确认显示“疑似黑屏”。
5. 对正常画面帧执行检测，确认显示正常。
6. 对帧号超出总帧数的视频，确认执行前或执行时给出明确错误。

验收标准：

- 帧号规则一致，界面使用 1-based，内部使用 0-based。
- 黑屏检测不会静默修改用户帧号。
- 疑似黑屏任务允许用户继续或修改。

### 阶段 3：封面抽取

目标：

- 对每个任务抽取指定帧为封面图。
- 输出命名稳定。
- 错误可追踪。

交付物：

- 封面抽取命令构造。
- FFmpeg 执行封装。
- 输出路径生成。
- 单任务封面处理状态。

验证步骤：

1. 使用短视频抽第 1 帧，确认输出图片正确。
2. 使用短视频抽中间帧，确认输出图片正确。
3. 使用含中文路径和空格路径的视频，确认输出成功。
4. 输出目录不存在时，确认自动创建。
5. 输出文件已存在且不允许覆盖时，确认任务提示冲突。
6. FFmpeg 返回错误时，确认任务失败并显示原因。

验收标准：

- 成功任务生成封面图。
- 失败任务不生成错误的成功记录。
- 路径包含中文和空格时正常工作。

### 阶段 4：去帧视频生成

目标：

- 删除目标帧后输出 MP4。
- 视频重新编码。
- 音频优先 copy，必要时 AAC 降级。

交付物：

- 去帧视频命令构造。
- 音频 copy 失败降级策略。
- 任务进度展示。
- 取消任务能力。

验证步骤：

1. 输入 100 帧视频，删除第 10 帧，输出视频应约为 99 帧。
2. 使用有音频视频处理，确认输出视频可播放且有声音。
3. 使用无音频视频处理，确认输出视频可播放。
4. 使用不同格式源视频处理，确认输出统一为 MP4。
5. 中途取消当前任务，确认 FFmpeg 子进程被终止。
6. 单个任务失败后，确认后续任务继续执行。

验收标准：

- 输出视频为 MP4。
- 目标帧被删除。
- 输出视频可正常播放。
- 失败不会中断整个队列。

### 阶段 5：结果报告与历史

目标：

- 生成 `result.json`。
- 生成 `result.csv`。
- 写入全局 `history.json`。
- 支持历史查询。

交付物：

- 结果写入模块。
- 历史模块。
- 历史页。
- 结果打开入口。

验证步骤：

1. 执行一批全部成功任务，确认 result 文件内容正确。
2. 执行一批包含失败任务的任务，确认失败原因写入 result。
3. 用 Excel 打开 result.csv，确认字段可读。
4. 重启应用，确认历史记录仍存在。
5. 删除某次 result.json，确认历史页显示结果文件不存在。
6. 通过历史记录重新加载输入目录和输出目录。

验收标准：

- result.json 可完整复盘一次运行。
- result.csv 适合人工查看。
- history.json 只保存摘要，不重复保存完整任务明细。

### 阶段 6：打包与发布验证

目标：

- 打包为 Windows 桌面程序。
- 验证无开发环境机器可运行。
- 决定是否内置 FFmpeg。

交付物：

- PyInstaller 打包脚本。
- 发布目录结构。
- 使用说明。
- FFmpeg 许可说明。

验证步骤：

1. 在开发机打包应用。
2. 在无 Python 环境的 Windows 机器运行。
3. 测试外部 FFmpeg 配置。
4. 测试内置 FFmpeg 路径。
5. 处理包含中文路径、空格路径、长文件名的视频。
6. 处理大文件视频，观察进度与取消是否正常。

验收标准：

- 用户双击即可启动。
- FFmpeg 可用状态清楚。
- 任务处理结果与开发环境一致。

## 11. 测试策略

### 11.1 单元测试

重点覆盖：

- 文件扩展名判断。
- 帧号 1-based 到 0-based 转换。
- 输出命名。
- 输出冲突判断。
- result.json 结构。
- result.csv 字段。
- history.json 追加逻辑。
- FFmpeg 错误解析。

### 11.2 集成测试

准备测试素材：

```text
samples/
  short_with_audio.mp4
  short_without_audio.mp4
  black_first_frame.mp4
  chinese path 测试.mp4
  fake_video.mp4
  readme.txt
```

集成验证：

- 扫描分类正确。
- 抽封面成功。
- 删除单帧成功。
- 黑屏检测提示正确。
- 结果文件正确。

### 11.3 手工验证清单

每次发布前手工验证：

1. 首次启动无配置。
2. FFmpeg 不存在。
3. FFmpeg 手动配置。
4. 输入目录为空。
5. 输入目录没有视频。
6. 输入目录混合视频和非视频。
7. 输出目录无权限。
8. 输出文件重名。
9. 任务中途取消。
10. 部分任务失败。
11. 全部任务成功。
12. 历史记录查询。

## 12. 风险与应对

### 12.1 单帧删除需要重新编码

风险：

- 处理速度慢。
- 输出体积变化。
- 画质可能轻微变化。

应对：

- 界面提示“去帧视频会重新编码”。
- 默认使用较高质量 CRF。
- 后续提供质量参数设置。

### 12.2 总帧数不一定准确

风险：

- 某些视频 ffprobe 无法快速获取准确总帧数。

应对：

- 总帧数未知时允许创建任务。
- 执行阶段捕获越界错误。
- 结果中明确记录失败原因。

### 12.3 黑屏检测可能误判

风险：

- 夜景、片头、字幕黑底可能被判定为疑似黑屏。

应对：

- 使用“疑似黑屏”提示。
- 不自动阻止任务。
- 允许用户单独修改帧号或继续执行。

### 12.4 音频 copy 兼容性

风险：

- 某些音频编码不能直接 copy 到 MP4。

应对：

- 失败后降级为 AAC 重试。
- 在 result.json 记录是否发生降级。

### 12.5 大文件处理耗时

风险：

- GUI 卡顿。
- 用户不知道是否仍在执行。

应对：

- 后台线程执行。
- 显示当前任务。
- 显示总进度。
- 支持取消。

## 13. 后续扩展方向

- 递归扫描子目录。
- 每个视频输出多张封面。
- 按时间点抽帧。
- 按百分比抽帧。
- 自动寻找非黑屏帧。
- 视频预览与帧预览。
- 自定义输出图片格式。
- 自定义视频编码质量。
- 批量导入配置表。
- 任务模板。
- 处理完成后自动打开输出目录。
- 历史记录搜索和筛选。

## 14. 第一版验收总标准

第一版完成时必须满足：

1. 用户可以选择一个混合文件目录。
2. 工具能准确区分视频和非视频。
3. 用户能设置统一目标帧号。
4. 用户能单独修改某个视频的目标帧号。
5. 工具能提示疑似黑屏帧。
6. 成功任务能输出封面图。
7. 成功任务能输出删除目标帧后的 MP4 视频。
8. 失败任务能展示明确失败原因。
9. 所有任务结束后能生成 `result.json`。
10. 所有任务结束后能生成 `result.csv`。
11. 历史页能查询曾经处理过的目录。
12. GUI 在处理期间不失去响应。
13. 任务失败不会中断整个批处理队列。
14. 路径包含中文和空格时能正常工作。

