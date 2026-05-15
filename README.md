# Video Highlight Editing Tools

`Video Highlight Editing Tools` 是一个面向 Windows 的本地视频剪辑工具，适合短剧剪辑、批量混剪、批量添加片头片尾等场景。

工具提供 Web UI 操作界面，核心处理在本机完成，依赖 `FFmpeg`，支持接入 OpenAI-compatible 视觉模型做剧情分析和精彩片段选择。

## 下载与安装

### 直接下载可运行版本

仓库内已提供 Windows 发布包：

`release/VideoMixerUI_JackLuo_GitHub_Release.zip`

使用方式：

1. 下载仓库中的 `release/VideoMixerUI_JackLuo_GitHub_Release.zip`
2. 解压整个压缩包
3. 双击 `VideoMixerUI.exe`
4. 程序会自动启动本地服务，并在浏览器中打开：

```text
http://127.0.0.1:8787
```

### 运行前要求

- Windows 系统
- 已安装 `FFmpeg`
- 如果要使用 AI 剧情剪辑或 AI 打码，需要准备对应模型的：
  - `API Base`
  - `API Key`
  - `模型名`

## 主要功能

### 1. 剧集精彩剪辑

- 选择多个视频后，按文件名排序
- 将多个视频视为一条连续剧情
- 由 AI 判断每个源视频中应该保留的连续片段
- 最终输出一个整体连贯成片
- 支持自定义最终成片总时长
- 结尾会尽量延长到人物说完当前一句话，并做画面和音频同步淡出

输出结果通常包括：

- `story_sequence.mp4`
- `story_plan.csv`
- `story_memory.json`

### 2. 混剪生成

- 将多个源视频切分成若干份
- 随机组合成多个不重复新视频
- 支持设置每个视频切几份
- 支持设置生成几个新视频
- 支持设置每个源视频开头、结尾排除秒数
- 支持限制切分片段不重复使用

### 3. 批量片头片尾

- 批量为主体视频添加统一片头
- 批量为主体视频添加统一片尾
- 可以只加片头、只加片尾，或两者都加

## AI 相关说明

剧集精彩剪辑强制使用 AI，不再使用本地规则兜底。

当前页面支持配置：

- `API Base` 预设
- `API Key`
- `模型名`
- 每多少秒抽帧
- 每个时间窗口抽多少帧
- 最大抽帧数
- 温度
- 重试次数
- 重试等待秒数

已内置常见 `API Base` 预设：

- OpenAI
- Gemini
- 阿里云 DashScope
- 智谱 GLM
- DeepSeek
- 硅基流动
- OpenRouter
- 自定义

如果 AI 调用失败，任务会立即停止，避免继续生成错误内容。

## 打码功能

支持使用单独视觉模型对最终生成的视频做裸露胸口相关画面模糊处理。

特点：

- 可单独开启或关闭
- 关闭时，相关打码设置会自动禁用
- 开启后会在最终成片生成后整体扫描并模糊对应区域

## 输出文件保存位置

每个功能页面都可以单独设置输出位置。

- 如果填写绝对路径，例如 `D:\story_output`，文件会保存到该目录
- 如果填写相对名称，例如 `story_output`，会保存到当前任务目录下
- 页面中的“选择”按钮可以直接打开文件夹选择窗口

## 关闭程序

如果程序已经启动并占用了本地端口 `8787`，可以使用仓库内提供的脚本关闭：

- `stop_video_mixer_service.bat`
- `stop_video_mixer_service.ps1`

## 源码文件说明

- `web_mixer.py`
  Web UI、本地服务、上传处理、任务调度

- `video_mixer.py`
  FFmpeg 调用、AI 分析、混剪、剧情剪辑、打码处理

- `VideoMixerUI.spec`
  PyInstaller 打包配置

- `version_info.txt`
  Windows 可执行文件版本信息

## 从源码运行

如果你想直接从源码启动：

```powershell
python .\web_mixer.py
```

然后在浏览器打开：

```text
http://127.0.0.1:8787
```

## 备注

- 所有视频处理都在本机完成
- 需要保留发布包中的 `_internal` 目录，不能只单独复制 `VideoMixerUI.exe`
- 如果是从 GitHub 下载发布包，请先完整解压后再运行

署名：`JackLuo`
