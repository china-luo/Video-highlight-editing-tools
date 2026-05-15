#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import random
import re
import shutil
import string
import subprocess
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import video_mixer

ROOT = Path(__file__).resolve().parent
JOB_ROOT = ROOT / "web_mixer_jobs"
HOST = "127.0.0.1"
PORT = 8787
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

APPLE_STYLE_INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>视频混剪工具</title>
<style>
:root{--page:#f5f5f7;--card:#fff;--ink:#1d1d1f;--muted:#6e6e73;--line:#d2d2d7;--blue:#0071e3;--blue2:#2997ff;--green:#0a7f45;--red:#b42318;--side:#f7f7f8;--side-hover:#ececf1;--shadow:0 18px 44px rgba(0,0,0,.08)}*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI","Microsoft YaHei",Arial,sans-serif;line-height:1.47}.topbar{position:sticky;top:0;z-index:5;height:44px;background:rgba(245,245,247,.82);backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid rgba(0,0,0,.08)}.topbar-inner{max-width:1320px;margin:0 auto;height:44px;padding:0 24px;display:flex;align-items:center;justify-content:space-between;font-size:13px}.brand{font-weight:700}.nav{display:flex;gap:22px;color:var(--muted)}.hero{text-align:center;padding:42px 20px 22px}.eyebrow{margin:0 0 8px;color:var(--muted);font-size:17px;font-weight:600}.hero h1{margin:0;font-size:52px;line-height:1.05;letter-spacing:0;font-weight:760}.hero p{max-width:760px;margin:14px auto 0;color:#424245;font-size:20px}.hero-actions{display:none}.pill{border:0;border-radius:999px;padding:10px 20px;min-height:40px;background:var(--blue);color:#fff;font:inherit;font-weight:600;cursor:pointer}.pill.secondary{background:transparent;color:var(--blue);box-shadow:inset 0 0 0 1px var(--blue)}.metrics{max-width:920px;margin:0 auto 26px;padding:0 20px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.metric{background:#fff;border-radius:18px;padding:18px;text-align:center;box-shadow:0 1px 2px rgba(0,0,0,.04)}.metric strong{display:block;font-size:30px;line-height:1.05}.metric span{display:block;margin-top:6px;color:var(--muted);font-size:13px}.workspace{max-width:1320px;margin:0 auto 64px;padding:0 24px;display:grid;grid-template-columns:232px minmax(0,1fr);gap:20px;align-items:start;transition:grid-template-columns .2s ease}.workspace.nav-collapsed{grid-template-columns:68px minmax(0,1fr)}.side-nav{position:sticky;top:62px;min-height:calc(100vh - 86px);background:var(--side);border-right:1px solid rgba(0,0,0,.08);border-radius:18px;padding:12px;display:flex;flex-direction:column;gap:10px;grid-row:1 / span 2;box-shadow:none;overflow:hidden}.side-top{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:36px}.side-title{margin:0 8px;color:var(--muted);font-size:12px;font-weight:700}.collapse-btn{width:36px;height:36px;border:0;border-radius:10px;background:transparent;color:#424245;font:inherit;font-size:18px;font-weight:700;cursor:pointer}.collapse-btn:hover{background:var(--side-hover)}.nav-items{display:grid;gap:4px}.nav-item{border:0;border-radius:10px;padding:11px 12px;min-height:42px;background:transparent;color:#2f3033;text-align:left;font:inherit;font-size:14px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:10px}.nav-item:hover{background:var(--side-hover)}.nav-item.active{background:#e7e7eb;color:#111}.nav-icon{width:22px;min-width:22px;text-align:center;font-weight:760;color:#68686d}.nav-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.workspace.nav-collapsed .side-title,.workspace.nav-collapsed .nav-label{display:none}.workspace.nav-collapsed .side-top{justify-content:center}.workspace.nav-collapsed .nav-item{justify-content:center;padding:11px 8px}.card{background:var(--card);border-radius:24px;box-shadow:var(--shadow);overflow:hidden}.status-card{grid-column:2;max-width:none}.card-head{padding:26px 30px 0}.card-head h2{margin:0;font-size:28px;line-height:1.12}.tab-panel{display:none}.tab-panel.active{display:block}form,.status{padding:22px 30px 30px;display:grid;gap:18px}.group-tabs{display:flex;gap:8px;overflow:auto;padding:4px 2px 2px;scrollbar-width:thin}.group-tab{border:0;border-radius:999px;padding:9px 14px;min-height:38px;background:#f0f0f2;color:#424245;font:inherit;font-size:13px;font-weight:700;cursor:pointer;white-space:nowrap}.group-tab:hover{background:#e8e8ed}.group-tab.active{background:#1d1d1f;color:#fff}.group-tab:disabled{opacity:.55;cursor:wait}.form-section{display:none;gap:16px;padding:20px;border:1px solid rgba(0,0,0,.06);border-radius:20px;background:#fbfbfd}.form-section.active{display:grid}.form-section h3{margin:0;font-size:17px;line-height:1.25;font-weight:760;color:#1d1d1f}.section-note{margin:-4px 0 0;color:var(--muted);font-size:13px}.status{gap:14px}.status-tools{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}label{display:grid;gap:7px;color:#1d1d1f;font-size:13px;font-weight:650}label.control-disabled{color:#9a9aa0}input,select{width:100%;border:1px solid transparent;border-radius:14px;padding:13px 14px;background:#f5f5f7;color:var(--ink);font:inherit;outline:none}input:disabled,select:disabled{opacity:.55;cursor:not-allowed}input:focus,select:focus{border-color:var(--blue2);box-shadow:0 0 0 4px rgba(0,113,227,.14)}input[type=file]{padding:12px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.path-picker{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end}.path-button{border:0;border-radius:999px;padding:11px 18px;min-height:44px;background:#1d1d1f;color:#fff;font:inherit;font-weight:650;cursor:pointer;white-space:nowrap}.checkline{display:flex;gap:10px;align-items:center;font-size:14px;font-weight:600}.checkline input{width:18px;height:18px;accent-color:var(--blue)}.hint{color:var(--muted);font-size:13px}.actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}button.submit{border:0;border-radius:999px;padding:12px 22px;min-height:44px;background:var(--blue);color:#fff;font:inherit;font-weight:700;cursor:pointer}button.secondary-control{border:0;border-radius:999px;padding:11px 18px;min-height:42px;background:#e8e8ed;color:#1d1d1f;font:inherit;font-weight:650;cursor:pointer}button:disabled{opacity:.55;cursor:wait}.badge{width:max-content;border-radius:999px;padding:6px 12px;background:#e8e8ed;color:#424245;font-size:13px;font-weight:700}.badge.running{background:#eaf4ff;color:#0066cc}.badge.done{background:#e8f7ef;color:var(--green)}.badge.error{background:#fdecec;color:var(--red)}.log{min-height:240px;max-height:380px;overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fbfbfd;color:#1d1d1f;padding:16px;white-space:pre-wrap;font-family:"SF Mono",Consolas,monospace;font-size:13px;box-shadow:inset 0 1px 0 rgba(255,255,255,.7)}.outputs{display:grid;gap:10px}.output-link{display:flex;justify-content:space-between;gap:12px;align-items:center;border-radius:16px;padding:13px 14px;color:var(--blue);text-decoration:none;background:#f5f5f7;overflow-wrap:anywhere}.output-link span{color:var(--muted);font-size:12px;white-space:nowrap}@media(max-width:1120px){.workspace{grid-template-columns:204px minmax(0,1fr)}.workspace.nav-collapsed{grid-template-columns:68px minmax(0,1fr)}.status-card{grid-column:2}.hero h1{font-size:42px}.hero p{font-size:18px}.metrics{grid-template-columns:1fr 1fr 1fr}}@media(max-width:760px){.nav{display:none}.hero{padding-top:34px}.hero h1{font-size:34px}.hero p{font-size:16px}.workspace,.workspace.nav-collapsed{grid-template-columns:1fr;padding:0 12px}.side-nav{position:static;min-height:auto;border-radius:18px;grid-row:auto}.workspace.nav-collapsed .side-title,.workspace.nav-collapsed .nav-label{display:inline}.workspace.nav-collapsed .nav-item{justify-content:flex-start;padding:11px 12px}.nav-items{grid-template-columns:1fr}.status-card{grid-column:auto}.metrics,.grid,.path-picker{grid-template-columns:1fr}.card{border-radius:22px}.card-head,form,.status{padding-left:18px;padding-right:18px}.form-section{padding:16px;border-radius:18px}.group-tabs{padding-bottom:4px}}
</style>
</head>
<body>
<header class="topbar"><div class="topbar-inner"><div class="brand">Video Mixer</div><nav class="nav"><span>混剪</span><span>片头片尾</span><span>剧集剪辑</span><span>By JackLuo</span></nav></div></header>
<section class="hero">
<p class="eyebrow">本地视频自动化工具</p>
<h1>视频混剪工具</h1>
<p>批量混剪、统一添加片头片尾、按集提取连续精彩段落。所有处理都在本机完成。</p>
<div class="hero-actions"><button class="pill" data-jump="storyPanel" type="button">剧集精彩剪辑</button><button class="pill secondary" data-jump="mixPanel" type="button">开始混剪</button><button class="pill secondary" data-jump="introOutroPanel" type="button">批量片头片尾</button></div>
</section>
<section class="metrics">
<div class="metric"><strong id="fileCount">0</strong><span>已选择视频</span></div>
<div class="metric"><strong id="clipEstimate">0</strong><span>预计可用片段</span></div>
<div class="metric"><strong id="outputEstimate">0</strong><span>计划生成成片</span></div>
</section>
<main class="workspace">
<aside class="side-nav">
<div class="side-top"><div class="side-title">功能</div><button class="collapse-btn" id="collapseNavBtn" type="button" title="折叠/展开侧边栏">☰</button></div>
<div class="nav-items"><button class="nav-item active" data-tab="storyPanel" type="button" title="剧集精彩剪辑"><span class="nav-icon">S</span><span class="nav-label">剧集精彩剪辑</span></button><button class="nav-item" data-tab="mixPanel" type="button" title="混剪生成"><span class="nav-icon">M</span><span class="nav-label">混剪生成</span></button><button class="nav-item" data-tab="introOutroPanel" type="button" title="批量片头片尾"><span class="nav-icon">B</span><span class="nav-label">批量片头片尾</span></button></div>
</aside>
<section class="card">
<div id="storyPanel" class="tab-panel active">
<div class="card-head"><h2>剧集精彩剪辑</h2></div>
<form id="storyForm" novalidate>
<input name="mode" type="hidden" value="story">
<div class="group-tabs" role="tablist" aria-label="剧集剪辑参数分组"><button class="group-tab active" data-group="story-source" type="button">素材与时长</button><button class="group-tab" data-group="story-output" type="button">输出画质</button><button class="group-tab" data-group="story-ai" type="button">AI 策略</button><button class="group-tab" data-group="story-censor" type="button">打码识别</button><button class="group-tab" data-group="story-run" type="button">执行说明</button></div>
<div class="form-section active" data-group-panel="story-source">
<h3>素材与时长</h3>
<label title="程序会按文件名排序作为剧情顺序，再整体裁剪成一个连贯视频。">剧情源视频<input id="storyFiles" name="story_files" type="file" multiple accept="video/*" required></label>
<div class="grid"><label title="最终输出的整个剧情剪辑视频总时长。AI 会按文件名顺序从每个源视频中选择适合剧情推进的片段。">最终成片总时长（秒）<input id="storyDuration" name="target_seconds" type="number" min="5" step="1" value="180" required></label><label title="记录本次整体剪辑的已选时间段和剧情摘要。">记忆文件名<input name="memory_name" type="text" value="story_memory.json"></label></div>
</div>
<div class="form-section" data-group-panel="story-output">
<h3>输出画质</h3>
<div class="grid"><label title="统一输出视频尺寸。不同源视频会缩放并补边到该尺寸。">输出比例<select id="storyRatio"><option value="1920x1080">横屏 1920x1080</option><option value="1080x1920">竖屏 1080x1920</option><option value="1280x720">横屏 1280x720</option><option value="720x1280">竖屏 720x1280</option></select></label><label title="统一输出帧率。建议保持 30，短视频平台常用。">帧率<input name="fps" type="number" min="1" value="30"></label></div>
<div class="grid"><label title="控制输出视频压缩质量。数值越低画质越高、文件越大；20 是常用平衡值。">画质 CRF<input name="crf" type="number" min="1" max="51" value="20"></label><label title="控制是否启用单独的打码视觉模型。开启后会让模型识别需要模糊的露胸/露沟区域，并用 FFmpeg 模糊对应画面区域。">打码识别<select name="censor_ai_enabled"><option value="off">关闭</option><option value="on">开启单独打码模型</option></select></label></div>
<div class="path-picker"><label title="成片、记忆文件和剪辑计划表会保存到这里。可填完整路径，也可填文件夹名。">输出位置<input id="storyOutPath" name="out_path" type="text" value="story_output" placeholder="例如 D:\story_output 或 story_output"></label><button class="path-button pick-dir" data-target="storyOutPath" type="button">选择</button></div>
</div>
<div class="form-section" data-group-panel="story-ai">
<h3>AI 剪辑策略</h3>
<div class="grid"><label title="剧集剪辑强制使用 AI。AI 出错会立即停止后续处理，不再使用本地规则。">AI 分析<select name="ai_enabled"><option value="on">开启，调用视觉模型</option></select></label><label title="用于识别精彩片段、剧情摘要、上下集衔接的视觉模型名称。">模型名<input name="ai_model" type="text" placeholder="例如 gpt-4.1-mini、gemini-2.5-flash、qwen-vl-plus"></label></div>
<div class="grid"><label title="常用 OpenAI-compatible 接口地址。Gemini 使用 Google 官方 OpenAI 兼容入口。">API Base 预设<select id="aiBasePreset"><option value="https://api.openai.com/v1">OpenAI</option><option value="https://generativelanguage.googleapis.com/v1beta/openai">Gemini</option><option value="https://dashscope.aliyuncs.com/compatible-mode/v1">阿里云 DashScope</option><option value="https://open.bigmodel.cn/api/paas/v4">智谱 GLM</option><option value="https://api.deepseek.com/v1">DeepSeek</option><option value="https://api.siliconflow.cn/v1">硅基流动</option><option value="https://openrouter.ai/api/v1">OpenRouter</option><option value="">自定义</option></select></label><label title="实际请求地址。程序会自动在末尾补 /chat/completions。">API Base<input id="aiApiBase" name="ai_api_base" type="text" value="https://api.openai.com/v1" placeholder="例如 https://api.openai.com/v1"></label></div>
<label title="视觉模型接口密钥。仅随本次任务提交给本地后端，不写入源码。">API Key<input name="ai_api_key" type="password" placeholder="仅本次任务使用，不写入源码"></label>
<div class="grid"><label title="抽帧时间窗口。比如填 10，表示每 10 秒作为一个分析窗口。静态场景可设 1-5 秒，长视频可设 5-10 秒。">每多少秒<input name="ai_sample_window_seconds" type="number" min="0.1" max="3600" step="0.1" value="1"></label><label title="每个时间窗口内抽取多少帧。比如每 10 秒抽 3 帧，就是每个 10 秒窗口均匀取 3 张图给 AI。">抽多少帧<input name="ai_frames_per_window" type="number" min="1" max="120" value="1"></label></div>
<div class="grid"><label title="安全上限，避免长视频高密度抽帧导致请求过大。实际抽帧达到上限后会停止继续抽。">最大抽帧数<input name="ai_max_frames" type="number" min="1" max="1200" value="80"></label><label title="模型随机性。剪辑判断建议较低，0.1-0.3 更稳定。">温度<input name="ai_temperature" type="number" min="0" max="1" step="0.1" value="0.2"></label></div>
<div class="grid"><label title="遇到 429/500/502/503/504 或网络超时时自动重试；重试用尽后仍会立即停止任务。">AI失败重试次数<input name="ai_retry_count" type="number" min="0" max="10" value="3"></label><label title="每次重试前等待的基础秒数。第 2 次会等待 2 倍，第 3 次会等待 3 倍。">重试等待秒数<input name="ai_retry_delay" type="number" min="0" max="300" step="1" value="10"></label></div>
</div>
<div class="form-section" data-group-panel="story-censor">
<h3>打码识别</h3>
<label title="打码视觉模型名称，可与精彩片段模型不同。最终成片生成后会整体扫描并模糊裸露胸口区域。">打码模型名<input name="censor_ai_model" type="text" placeholder="例如 gpt-4.1-mini、gemini-2.5-flash"></label>
<div class="grid"><label title="打码视觉模型 API 地址。留空则默认使用上方 AI API Base。">打码 API Base<input name="censor_ai_api_base" type="text" placeholder="留空则使用上方 API Base"></label><label title="打码视觉模型 API Key。留空则默认使用上方 API Key。">打码 API Key<input name="censor_ai_api_key" type="password" placeholder="留空则使用上方 API Key"></label></div>
</div>
<div class="form-section" data-group-panel="story-run">
<h3>执行说明</h3>
<p class="hint">开启 AI 后会先按文件名排序，再把所有源视频当作一条连续剧情整体裁剪，只保留核心主线；最终结尾会尽量等人物说完当前话语，并给画面和音频同步淡出；如果开启打码识别，会在最终成片生成后整体扫描裸露胸口区域并统一模糊；AI 出错会立即停止后续工作。</p>
<div class="actions"><button class="submit" id="storySubmit" type="submit">开始剧集剪辑</button></div>
</div>
</form>
</div>
<div id="mixPanel" class="tab-panel">
<div class="card-head"><h2>混剪设置</h2></div>
<form id="mixForm" novalidate>
<input name="mode" type="hidden" value="mix">
<div class="group-tabs" role="tablist" aria-label="混剪参数分组"><button class="group-tab active" data-group="mix-source" type="button">素材与切分</button><button class="group-tab" data-group="mix-output" type="button">输出画质</button><button class="group-tab" data-group="mix-run" type="button">执行说明</button></div>
<div class="form-section active" data-group-panel="mix-source">
<h3>素材与切分</h3>
<label>源视频<input id="mixFiles" name="files" type="file" multiple accept="video/*" required></label>
<div class="grid"><label>每个视频切成几份<input id="parts" name="parts" type="number" min="1" value="5" required></label><label>生成几个新视频<input id="outputs" name="outputs" type="number" min="1" value="3" required></label></div>
<div class="grid"><label>每个新视频几个片段<input id="clipsPerOutput" name="clips_per_output" type="number" min="1" value="4" required></label><label>每个源视频开头排除秒数<input name="trim_head_seconds" type="number" min="0" step="0.1" value="0"></label></div>
<div class="grid"><label>每个源视频结尾排除秒数<input name="trim_tail_seconds" type="number" min="0" step="0.1" value="0"></label><label>随机种子<input name="seed" type="text" placeholder="留空则每次不同"></label></div>
<label class="checkline"><input name="no_reuse" type="checkbox">同一个切分片段只使用一次</label>
</div>
<div class="form-section" data-group-panel="mix-output">
<h3>输出画质</h3>
<div class="grid"><label>输出比例<select id="mixRatio"><option value="1920x1080">横屏 1920x1080</option><option value="1080x1920">竖屏 1080x1920</option><option value="1280x720">横屏 1280x720</option><option value="720x1280">竖屏 720x1280</option></select></label><label>帧率<input name="fps" type="number" min="1" value="30"></label></div>
<div class="grid"><label>画质 CRF<input name="crf" type="number" min="1" max="51" value="20"></label><label>输出命名<input type="text" value="mixed_001.mp4" disabled></label></div>
<div class="path-picker"><label>输出位置<input id="mixOutPath" name="out_path" type="text" value="mixed_output" placeholder="例如 D:\mix_output 或 mixed_output"></label><button class="path-button pick-dir" data-target="mixOutPath" type="button">选择</button></div>
</div>
<div class="form-section" data-group-panel="mix-run">
<h3>执行说明</h3>
<p class="hint">开头/结尾排除秒数会应用到每一段源视频；例如开头填 2、结尾填 3，则每个源视频前 2 秒和最后 3 秒不会参与切分和拼接。</p>
<div class="actions"><button class="submit" id="mixSubmit" type="submit">开始混剪</button></div>
</div>
</form>
</div>
<div id="introOutroPanel" class="tab-panel">
<div class="card-head"><h2>批量片头片尾</h2></div>
<form id="introOutroForm" novalidate>
<input name="mode" type="hidden" value="intro_outro">
<div class="group-tabs" role="tablist" aria-label="片头片尾参数分组"><button class="group-tab active" data-group="batch-source" type="button">素材选择</button><button class="group-tab" data-group="batch-output" type="button">输出画质</button><button class="group-tab" data-group="batch-run" type="button">执行说明</button></div>
<div class="form-section active" data-group-panel="batch-source">
<h3>素材选择</h3>
<label>主体视频<input id="batchFiles" name="base_files" type="file" multiple accept="video/*" required></label>
<div class="grid"><label>片头视频<input name="intro_file" type="file" accept="video/*"></label><label>片尾视频<input name="outro_file" type="file" accept="video/*"></label></div>
</div>
<div class="form-section" data-group-panel="batch-output">
<h3>输出画质</h3>
<div class="grid"><label>输出比例<select id="batchRatio"><option value="1920x1080">横屏 1920x1080</option><option value="1080x1920">竖屏 1080x1920</option><option value="1280x720">横屏 1280x720</option><option value="720x1280">竖屏 720x1280</option></select></label><label>帧率<input name="fps" type="number" min="1" value="30"></label></div>
<div class="grid"><label>画质 CRF<input name="crf" type="number" min="1" max="51" value="20"></label><label>输出文件夹名<input name="out_folder_name" type="text" value="intro_outro_output"></label></div>
<div class="path-picker"><label>输出位置<input id="batchOutPath" name="out_path" type="text" value="intro_outro_output" placeholder="例如 D:\batch_output 或 intro_outro_output"></label><button class="path-button pick-dir" data-target="batchOutPath" type="button">选择</button></div>
</div>
<div class="form-section" data-group-panel="batch-run">
<h3>执行说明</h3>
<p class="hint">可以只选片头、只选片尾，也可以两者都选。每个主体视频都会生成一个新视频。</p>
<div class="actions"><button class="submit" id="batchSubmit" type="submit">开始批量处理</button></div>
</div>
</form>
</div>
</section>
<section class="card status-card">
<div class="card-head"><h2>运行状态</h2></div>
<div class="status">
<div class="status-tools"><div id="badge" class="badge">等待开始</div><button class="secondary-control" id="resetBtn" type="button">重置状态</button></div>
<div id="outputsList" class="outputs"></div>
<div id="log" class="log">选择功能和视频后，这里会显示进度。</div>
</div>
</section>
</main>
<script>
const workspace=document.querySelector('.workspace');const collapseNavBtn=document.getElementById('collapseNavBtn');const storyForm=document.getElementById('storyForm');const mixForm=document.getElementById('mixForm');const introOutroForm=document.getElementById('introOutroForm');const storyFiles=document.getElementById('storyFiles');const storyDuration=document.getElementById('storyDuration');const mixFiles=document.getElementById('mixFiles');const batchFiles=document.getElementById('batchFiles');const parts=document.getElementById('parts');const outputs=document.getElementById('outputs');const clipsPerOutput=document.getElementById('clipsPerOutput');const fileCount=document.getElementById('fileCount');const clipEstimate=document.getElementById('clipEstimate');const outputEstimate=document.getElementById('outputEstimate');const badge=document.getElementById('badge');const log=document.getElementById('log');const outputsList=document.getElementById('outputsList');const resetBtn=document.getElementById('resetBtn');const aiBasePreset=document.getElementById('aiBasePreset');const aiApiBase=document.getElementById('aiApiBase');let pollTimer=null;let activeSubmit=null;let uiBusy=false;
const censorToggle=storyForm.querySelector('[name="censor_ai_enabled"]');const censorControlNames=['censor_ai_model','censor_ai_api_base','censor_ai_api_key'];
function updateCensorControls(){const storyActive=document.getElementById('storyPanel').classList.contains('active');const enabled=!uiBusy&&storyActive&&censorToggle&&censorToggle.value==='on';censorControlNames.forEach(name=>storyForm.querySelectorAll(`[name="${name}"]`).forEach(control=>{control.disabled=!enabled;const label=control.closest('label');if(label)label.classList.toggle('control-disabled',!enabled)}))}
function setPanelEnabled(){document.querySelectorAll('.tab-panel').forEach(panel=>{const active=panel.classList.contains('active');panel.querySelectorAll('input,select,button,textarea').forEach(control=>{control.disabled=uiBusy||!active})});document.querySelectorAll('.nav-item,[data-jump],#resetBtn,#collapseNavBtn').forEach(control=>{control.disabled=uiBusy});updateCensorControls()}
function setUiBusy(busy){uiBusy=busy;setPanelEnabled()}
function activateTab(id){if(uiBusy)return;document.querySelectorAll('.nav-item').forEach(t=>t.classList.toggle('active',t.dataset.tab===id));document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.id===id));setPanelEnabled();updateEstimate();workspace.scrollIntoView({behavior:'smooth',block:'start'});}
function activateGroup(button){if(uiBusy)return;const form=button.closest('form');const group=button.dataset.group;form.querySelectorAll('.group-tab').forEach(tab=>tab.classList.toggle('active',tab===button));form.querySelectorAll('.form-section').forEach(section=>section.classList.toggle('active',section.dataset.groupPanel===group))}
function updateEstimate(){const storyActive=document.getElementById('storyPanel').classList.contains('active');const mixActive=document.getElementById('mixPanel').classList.contains('active');if(storyActive){const count=storyFiles.files.length;fileCount.textContent=count;clipEstimate.textContent=storyDuration.value?`${storyDuration.value}s 总时长`:'-';outputEstimate.textContent=count?1:0}else if(mixActive){const count=mixFiles.files.length;fileCount.textContent=count;clipEstimate.textContent=count*Number(parts.value||0);outputEstimate.textContent=outputs.value||'0'}else{const count=batchFiles.files.length;fileCount.textContent=count;clipEstimate.textContent='-';outputEstimate.textContent=count}}
function setBadge(status){badge.className='badge';if(status==='running'){badge.classList.add('running');badge.textContent='正在处理'}else if(status==='done'){badge.classList.add('done');badge.textContent='已完成'}else if(status==='error'){badge.classList.add('error');badge.textContent='出错'}else{badge.textContent='等待开始'}}
function renderJob(job){setBadge(job.status);log.textContent=(job.logs||[]).join('\n')||'等待输出...';log.scrollTop=log.scrollHeight;outputsList.innerHTML='';for(const item of job.outputs||[]){const a=document.createElement('a');a.className='output-link';a.href=item.url;a.target='_blank';a.innerHTML=`<strong>${item.name}</strong><span>打开</span>`;outputsList.appendChild(a)}}
async function poll(jobId){const response=await fetch(`/api/jobs/${jobId}`);const job=await response.json();renderJob(job);if(job.status==='done'||job.status==='error'){clearInterval(pollTimer);pollTimer=null;setUiBusy(false);if(job.status==='done'){alert('剪辑已完成。')}else{const message=(job.error||((job.logs||[]).slice(-1)[0])||'剪辑失败');alert(`剪辑出错：\n${message}`)}}return job.status}
async function submitJob(event,ratioId,submitButton){event.preventDefault();if(uiBusy)return;const data=new FormData(event.currentTarget);const ratio=document.getElementById(ratioId).value.split('x');data.set('width',ratio[0]);data.set('height',ratio[1]);activeSubmit=submitButton;setUiBusy(true);setBadge('running');const selectedFiles=[...event.currentTarget.querySelectorAll('input[type=file]')].flatMap(input=>[...input.files]);const totalSize=selectedFiles.reduce((sum,file)=>sum+file.size,0);log.textContent=`正在上传 ${selectedFiles.length} 个视频，约 ${(totalSize/1024/1024).toFixed(1)} MB，请不要关闭页面...`;outputsList.innerHTML='';try{const response=await fetch('/api/jobs',{method:'POST',body:data});let body={};try{body=await response.json()}catch(parseError){throw new Error('服务没有返回有效响应，可能是上传中断或文件过大。')}if(!response.ok)throw new Error(body.error||'启动失败');const status=await poll(body.job_id);if(status!=='done'&&status!=='error'){pollTimer=setInterval(()=>poll(body.job_id).catch(error=>{clearInterval(pollTimer);pollTimer=null;setUiBusy(false);setBadge('error');log.textContent=error.message;alert(`剪辑出错：\n${error.message}`)}),1200)}}catch(error){setUiBusy(false);setBadge('error');log.textContent=error.message;alert(`剪辑出错：\n${error.message}`)}}
document.querySelectorAll('.nav-item').forEach(button=>button.addEventListener('click',()=>activateTab(button.dataset.tab)));document.querySelectorAll('.group-tab').forEach(button=>button.addEventListener('click',()=>activateGroup(button)));document.querySelectorAll('[data-jump]').forEach(button=>button.addEventListener('click',()=>activateTab(button.dataset.jump)));collapseNavBtn.addEventListener('click',()=>{if(uiBusy)return;workspace.classList.toggle('nav-collapsed');collapseNavBtn.textContent=workspace.classList.contains('nav-collapsed')?'›':'☰'});
storyForm.addEventListener('submit',e=>submitJob(e,'storyRatio',document.getElementById('storySubmit')));mixForm.addEventListener('submit',e=>submitJob(e,'mixRatio',document.getElementById('mixSubmit')));introOutroForm.addEventListener('submit',e=>submitJob(e,'batchRatio',document.getElementById('batchSubmit')));
resetBtn.addEventListener('click',()=>{if(uiBusy)return;if(pollTimer)clearInterval(pollTimer);pollTimer=null;setUiBusy(false);setBadge('idle');outputsList.innerHTML='';log.textContent='选择功能和视频后，这里会显示进度。'});
document.querySelectorAll('.pick-dir').forEach(button=>button.addEventListener('click',async()=>{if(uiBusy)return;button.disabled=true;const oldText=button.textContent;button.textContent='选择中';const controller=new AbortController();const timeoutId=setTimeout(()=>controller.abort(),65000);try{const response=await fetch('/api/select-folder',{signal:controller.signal});const body=await response.json();if(!response.ok)throw new Error(body.error||'没有选择文件夹');if(body.path)document.getElementById(button.dataset.target).value=body.path}catch(error){log.textContent=error.name==='AbortError'?'选择窗口超时，请再点一次“选择”。':error.message;setBadge('idle')}finally{clearTimeout(timeoutId);button.disabled=false;button.textContent=oldText;setPanelEnabled()}}));
aiBasePreset.addEventListener('change',()=>{if(aiBasePreset.value){aiApiBase.value=aiBasePreset.value}else{aiApiBase.focus()}});if(censorToggle)censorToggle.addEventListener('change',updateCensorControls);[storyFiles,mixFiles,batchFiles,storyDuration,parts,outputs,clipsPerOutput].forEach(el=>el.addEventListener('input',updateEstimate));storyFiles.addEventListener('change',updateEstimate);mixFiles.addEventListener('change',updateEstimate);batchFiles.addEventListener('change',updateEstimate);setPanelEnabled();updateEstimate();
</script>
</body>
</html>"""

def make_job_id() -> str:
    alphabet = string.ascii_lowercase + string.digits
    while True:
        job_id = "".join(random.choice(alphabet) for _ in range(10))
        if job_id not in JOBS:
            return job_id


def parse_content_disposition(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, quoted, plain in re.findall(r';\s*([^=]+)=(?:"([^"]*)"|([^;]*))', value or ""):
        result[key.strip().lower()] = (quoted or plain).strip()
    return result


def parse_multipart_stream(
    stream,
    content_type: str,
    content_length: int,
    job_id: str,
) -> tuple[dict[str, str], dict[str, list[Path]]]:
    match = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type)
    if not match:
        raise ValueError("上传请求缺少 multipart boundary。")
    boundary = ("--" + (match.group(1) or match.group(2)).strip()).encode("utf-8")
    final_boundary = boundary + b"--"
    input_root = JOB_ROOT / job_id / "inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    fields: dict[str, str] = {}
    grouped: dict[str, list[Path]] = {}
    file_index = 0
    bytes_read = 0

    def read_line() -> bytes:
        nonlocal bytes_read
        line = stream.readline()
        bytes_read += len(line)
        if content_length and bytes_read > content_length + 4096:
            raise ValueError("上传数据长度异常。")
        return line

    line = read_line()
    while line and not line.startswith(boundary):
        line = read_line()
    if not line:
        raise ValueError("没有读取到上传内容。")

    while line and not line.startswith(final_boundary):
        headers: dict[str, str] = {}
        while True:
            line = read_line()
            if line in (b"\r\n", b"\n", b""):
                break
            text = line.decode("utf-8", errors="replace")
            if ":" in text:
                key, value = text.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        disposition = parse_content_disposition(headers.get("content-disposition", ""))
        field_name = disposition.get("name", "files") or "files"
        filename = Path(disposition.get("filename", "")).name
        target = None
        handle = None
        buffer = bytearray()
        if filename:
            suffix = Path(filename).suffix.lower()
            if suffix not in video_mixer.VIDEO_EXTENSIONS:
                raise ValueError(f"不支持的视频格式：{filename}")
            file_index += 1
            target = input_root / f"{file_index:03d}_{filename}"
            handle = target.open("wb")

        previous = None
        try:
            while True:
                line = read_line()
                if not line:
                    raise ValueError("上传数据不完整，连接提前结束。")
                if line.startswith(boundary):
                    if previous is not None:
                        payload = previous[:-2] if previous.endswith(b"\r\n") else previous[:-1] if previous.endswith(b"\n") else previous
                        if handle:
                            handle.write(payload)
                        else:
                            buffer.extend(payload)
                    break
                if previous is not None:
                    if handle:
                        handle.write(previous)
                    else:
                        buffer.extend(previous)
                previous = line
        finally:
            if handle:
                handle.close()

        if target is not None:
            grouped.setdefault(field_name, []).append(target)
        else:
            fields[field_name] = bytes(buffer).decode("utf-8", errors="replace")

        if line.startswith(final_boundary):
            break

    if not grouped:
        raise ValueError("请选择至少一个视频。")
    return fields, grouped


def resolve_output_dir(job_dir: Path, value: str) -> Path:
    text = value.strip() or "output"
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch in "-_ .").strip()
    return (job_dir / (cleaned or "output")).resolve()


def choose_folder_with_windows_dialog() -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.askdirectory(parent=root, title="选择输出文件夹", mustexist=False)
        root.update()
        return selected
    finally:
        root.destroy()


def job_log(job_id: str, line: str) -> None:
    with JOBS_LOCK:
        JOBS[job_id]["logs"].append(line)


def set_job(job_id: str, **updates) -> None:
    with JOBS_LOCK:
        JOBS[job_id].update(updates)


def collect_outputs(job_id: str, out_dir: Path) -> tuple[list[dict], list[dict]]:
    output_files = []
    outputs_payload = []
    for path in sorted(out_dir.iterdir()):
        if path.suffix.lower() in {".mp4", ".csv"}:
            index = len(output_files)
            output_files.append({"path": str(path.resolve()), "name": path.name})
            outputs_payload.append({"name": path.name, "url": f"/outputs/{job_id}/{index}"})
    return output_files, outputs_payload


def run_mix_job(job_id: str, grouped_files: dict[str, list[Path]], fields: dict[str, str]) -> None:
    input_paths = grouped_files.get("files", [])
    parts = int(fields.get("parts", "5"))
    outputs = int(fields.get("outputs", "3"))
    clips_per_output = int(fields.get("clips_per_output", "0") or "0") or len(input_paths)
    width = int(fields.get("width", "1920"))
    height = int(fields.get("height", "1080"))
    fps = int(fields.get("fps", "30"))
    crf = int(fields.get("crf", "20"))
    seed_text = fields.get("seed", "").strip()
    seed = int(seed_text) if seed_text else None
    no_reuse = fields.get("no_reuse") == "on"
    trim_head_seconds = float(fields.get("trim_head_seconds", "0") or "0")
    trim_tail_seconds = float(fields.get("trim_tail_seconds", "0") or "0")
    if min(parts, outputs, clips_per_output, width, height, fps) < 1 or trim_head_seconds < 0 or trim_tail_seconds < 0:
        raise ValueError("Invalid numeric parameter.")

    out_dir = resolve_output_dir(JOB_ROOT / job_id, fields.get("out_path", "mixed_output"))
    job_log(job_id, f"读取 {len(input_paths)} 个源视频")
    clips = video_mixer.build_clip_pool(input_paths, parts, 0.5, trim_head_seconds, trim_tail_seconds, lambda msg: job_log(job_id, msg))
    job_log(job_id, f"已切分出 {len(clips)} 个候选片段")
    recipes = video_mixer.choose_recipes(clips, outputs, clips_per_output, no_reuse, random.Random(seed))
    job_log(job_id, f"已生成 {len(recipes)} 个不重复拼接方案")
    video_mixer.render_recipes(recipes, out_dir, width, height, fps, crf, lambda msg: job_log(job_id, msg))
    output_files, outputs_payload = collect_outputs(job_id, out_dir)
    job_log(job_id, f"完成，输出目录：{out_dir}")
    set_job(job_id, status="done", outputs=outputs_payload, output_files=output_files)


def run_intro_outro_job(job_id: str, grouped_files: dict[str, list[Path]], fields: dict[str, str]) -> None:
    base_videos = grouped_files.get("base_files", [])
    intro_videos = grouped_files.get("intro_file", [])
    outro_videos = grouped_files.get("outro_file", [])
    if not base_videos:
        raise ValueError("Select at least one base video.")
    intro_video = intro_videos[0] if intro_videos else None
    outro_video = outro_videos[0] if outro_videos else None
    if intro_video is None and outro_video is None:
        raise ValueError("Select an intro video, an outro video, or both.")

    width = int(fields.get("width", "1920"))
    height = int(fields.get("height", "1080"))
    fps = int(fields.get("fps", "30"))
    crf = int(fields.get("crf", "20"))
    if min(width, height, fps) < 1:
        raise ValueError("Invalid output size or fps.")

    out_dir = resolve_output_dir(JOB_ROOT / job_id, fields.get("out_path", "intro_outro_output"))
    job_log(job_id, f"主体视频：{len(base_videos)} 个")
    if intro_video is not None:
        job_log(job_id, f"片头：{intro_video.name}")
    if outro_video is not None:
        job_log(job_id, f"片尾：{outro_video.name}")
    video_mixer.render_intro_outro_batch(
        base_videos,
        intro_video,
        outro_video,
        out_dir,
        width,
        height,
        fps,
        crf,
        lambda msg: job_log(job_id, msg),
    )
    output_files, outputs_payload = collect_outputs(job_id, out_dir)
    job_log(job_id, f"完成，输出目录：{out_dir}")
    set_job(job_id, status="done", outputs=outputs_payload, output_files=output_files)


def run_story_job(job_id: str, grouped_files: dict[str, list[Path]], fields: dict[str, str]) -> None:
    source_videos = grouped_files.get("story_files", [])
    if not source_videos:
        raise ValueError("Select at least one story source video.")

    target_seconds = float(fields.get("target_seconds", "60") or "60")
    width = int(fields.get("width", "1920"))
    height = int(fields.get("height", "1080"))
    fps = int(fields.get("fps", "30"))
    crf = int(fields.get("crf", "20"))
    censor_mode = "none"
    if min(width, height, fps) < 1 or target_seconds <= 0:
        raise ValueError("Invalid story edit parameters.")

    out_dir = resolve_output_dir(JOB_ROOT / job_id, fields.get("out_path", "story_output"))
    memory_name = fields.get("memory_name", "story_memory.json").strip() or "story_memory.json"
    safe_memory = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in memory_name).strip()
    memory_path = out_dir / (safe_memory or "story_memory.json")

    source_videos = sorted(source_videos, key=lambda item: item.name.lower())
    job_log(job_id, f"剧情源视频：{len(source_videos)} 个，已按文件名排序")
    job_log(job_id, f"最终成片总时长：{target_seconds:g} 秒")
    job_log(job_id, f"打码模式：{censor_mode}")
    ai_config = {
        "enabled": fields.get("ai_enabled") == "on",
        "api_base": fields.get("ai_api_base", "").strip(),
        "api_key": fields.get("ai_api_key", "").strip(),
        "model": fields.get("ai_model", "").strip(),
        "sample_window_seconds": float(fields.get("ai_sample_window_seconds", "1") or "1"),
        "frames_per_window": int(fields.get("ai_frames_per_window", "1") or "1"),
        "max_frames": int(fields.get("ai_max_frames", "80") or "80"),
        "temperature": float(fields.get("ai_temperature", "0.2") or "0.2"),
        "retry_count": int(fields.get("ai_retry_count", "3") or "3"),
        "retry_delay": float(fields.get("ai_retry_delay", "10") or "10"),
        "timeout": 90,
    }
    if not (ai_config["enabled"] and ai_config["api_base"] and ai_config["api_key"] and ai_config["model"]):
        raise ValueError("剧集剪辑必须完整配置 AI：API Base、API Key、模型名。")
    job_log(job_id, f"AI 分析：开启，模型 {ai_config['model']}")
    job_log(
        job_id,
        f"AI 抽帧：每 {ai_config['sample_window_seconds']} 秒抽 "
        f"{ai_config['frames_per_window']} 帧，最多 {ai_config['max_frames']} 帧/视频",
    )

    job_log(
        job_id,
        f"AI retry: up to {ai_config['retry_count']} time(s), base wait {ai_config['retry_delay']:g}s",
    )

    censor_config = {
        "enabled": fields.get("censor_ai_enabled") == "on",
        "api_base": (fields.get("censor_ai_api_base", "").strip() or ai_config["api_base"]),
        "api_key": (fields.get("censor_ai_api_key", "").strip() or ai_config["api_key"]),
        "model": (fields.get("censor_ai_model", "").strip() or ai_config["model"]),
        "sample_window_seconds": float(fields.get("ai_sample_window_seconds", "1") or "1"),
        "frames_per_window": int(fields.get("ai_frames_per_window", "1") or "1"),
        "max_frames": min(max(int(fields.get("ai_max_frames", "80") or "80"), 80), 300),
        "temperature": 0.1,
        "retry_count": int(fields.get("ai_retry_count", "3") or "3"),
        "retry_delay": float(fields.get("ai_retry_delay", "10") or "10"),
        "timeout": 90,
    }
    if censor_config["enabled"]:
        if not (censor_config["api_base"] and censor_config["api_key"] and censor_config["model"]):
            raise ValueError("打码模型已开启，但配置不完整。")
        job_log(job_id, f"打码 AI：开启，模型 {censor_config['model']}")
    else:
        job_log(job_id, "打码 AI：关闭")
    video_mixer.render_story_sequence(
        source_videos,
        out_dir,
        target_seconds,
        width,
        height,
        fps,
        crf,
        censor_mode,
        memory_path,
        ai_config,
        censor_config,
        lambda msg: job_log(job_id, msg),
    )
    output_files, outputs_payload = collect_outputs(job_id, out_dir)
    job_log(job_id, f"完成，输出目录：{out_dir}")
    set_job(job_id, status="done", outputs=outputs_payload, output_files=output_files)


def run_job(job_id: str, grouped_files: dict[str, list[Path]], fields: dict[str, str]) -> None:
    try:
        video_mixer.require_tool("ffmpeg")
        video_mixer.require_tool("ffprobe")
        mode = fields.get("mode", "mix")
        if "story_files" in grouped_files:
            mode = "story"
        elif "base_files" in grouped_files:
            mode = "intro_outro"
        if mode == "story":
            run_story_job(job_id, grouped_files, fields)
        elif mode == "intro_outro":
            run_intro_outro_job(job_id, grouped_files, fields)
        else:
            run_mix_job(job_id, grouped_files, fields)
    except subprocess.CalledProcessError as error:
        message = error.stderr or error.stdout or str(error)
        set_job(job_id, status="error", error=message)
        job_log(job_id, message)
    except Exception as error:
        message = str(error)
        set_job(job_id, status="error", error=message)
        job_log(job_id, message)
        job_log(job_id, traceback.format_exc())


class Handler(BaseHTTPRequestHandler):
    server_version = "VideoMixerWeb/3.0"

    def log_message(self, format: str, *args) -> None:
        return

    def send_bytes(self, data: bytes, content_type: str, status=HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict, status=HTTPStatus.OK) -> None:
        self.send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_bytes(APPLE_STYLE_INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/select-folder":
            try:
                selected = choose_folder_with_windows_dialog()
                if selected:
                    self.send_json({"path": selected})
                else:
                    self.send_json({"error": "未选择文件夹"}, HTTPStatus.BAD_REQUEST)
            except Exception as error:
                self.send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                payload = dict(job) if job else None
            self.send_json(payload or {"error": "任务不存在"}, HTTPStatus.OK if payload else HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/outputs/"):
            parts = [unquote(part) for part in parsed.path.split("/") if part]
            if len(parts) != 3:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            _, job_id, index_text = parts
            try:
                index = int(index_text)
            except ValueError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                files = job.get("output_files", []) if job else []
            if index < 0 or index >= len(files):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            target = Path(files[index]["path"]).resolve()
            if not target.exists():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = "video/mp4" if target.suffix.lower() == ".mp4" else "text/csv; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(target.stat().st_size))
            self.send_header("Content-Disposition", f'attachment; filename="{html.escape(target.name)}"')
            self.end_headers()
            with target.open("rb") as handle:
                shutil.copyfileobj(handle, self.wfile)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/jobs":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                raise ValueError("Invalid request format.")
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            if content_length <= 0:
                raise ValueError("没有读取到上传数据。")
            job_id = make_job_id()
            fields, grouped_files = parse_multipart_stream(self.rfile, content_type, content_length, job_id)
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "job_id": job_id,
                    "status": "running",
                    "logs": [f"任务已创建，已接收 {sum(len(v) for v in grouped_files.values())} 个视频，准备分析..."],
                    "outputs": [],
                    "output_files": [],
                }
            threading.Thread(target=run_job, args=(job_id, grouped_files, fields), daemon=True).start()
            self.send_json({"job_id": job_id})
        except Exception as error:
            message = str(error) or type(error).__name__
            try:
                (JOB_ROOT / "startup_errors.log").open("a", encoding="utf-8").write(message + "\n" + traceback.format_exc() + "\n")
            except Exception:
                pass
            self.send_json({"error": message}, HTTPStatus.BAD_REQUEST)


def main() -> None:
    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    url = f"http://{HOST}:{PORT}"
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        webbrowser.open(url)
        return
    print(f"Video Mixer UI: {url}")
    threading.Thread(target=lambda: (time.sleep(0.8), webbrowser.open(url)), daemon=True).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
