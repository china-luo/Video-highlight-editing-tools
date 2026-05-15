#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import random
import base64
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
PATH_REFRESHED = False
TRANSIENT_AI_HTTP_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Clip:
    id: str
    source: Path
    start: float
    duration: float
    has_audio: bool


def refresh_windows_path() -> None:
    global PATH_REFRESHED
    if PATH_REFRESHED or platform.system() != "Windows":
        return
    PATH_REFRESHED = True
    try:
        import winreg

        values = []
        for hive, key_path in [
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ]:
            with winreg.OpenKey(hive, key_path) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, "Path")
                    values.append(value)
                except FileNotFoundError:
                    pass
        if values:
            os.environ["Path"] = os.environ.get("Path", "") + os.pathsep + os.pathsep.join(values)
    except OSError:
        pass


def startup_options() -> dict:
    if platform.system() != "Windows":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": startupinfo, "creationflags": subprocess.CREATE_NO_WINDOW}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **startup_options(),
    )


def require_tool(name: str) -> None:
    refresh_windows_path()
    if shutil.which(name) is None:
        raise RuntimeError(f"找不到 {name}。请确认 FFmpeg 已安装，并且 {name} 可以在 PowerShell 中运行。")


def ffprobe_json(path: Path) -> dict:
    refresh_windows_path()
    fd, temp_name = tempfile.mkstemp(prefix="ffprobe_", suffix=".json")
    os.close(fd)
    temp_path = Path(temp_name)
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        with temp_path.open("w", encoding="utf-8", errors="replace") as output:
            result = subprocess.run(
                command,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=output,
                stderr=subprocess.PIPE,
                **startup_options(),
            )
        text = temp_path.read_text(encoding="utf-8", errors="replace").strip()
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe 读取失败：{path}\n{result.stderr.strip()}")
        if not text:
            raise RuntimeError(f"ffprobe 没有返回视频信息：{path}")
        return json.loads(text)
    finally:
        temp_path.unlink(missing_ok=True)


def media_info(path: Path) -> tuple[float, bool]:
    data = ffprobe_json(path)
    duration = float(data.get("format", {}).get("duration") or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    if duration <= 0:
        raise RuntimeError(f"无法读取视频时长：{path}")
    return duration, has_audio


def build_clip_pool(
    inputs: list[Path],
    parts: int,
    min_clip_seconds: float,
    trim_head_seconds: float,
    trim_tail_seconds: float,
    log=print,
) -> list[Clip]:
    clips: list[Clip] = []
    for source in inputs:
        duration, has_audio = media_info(source)
        trim_head = max(0.0, trim_head_seconds)
        trim_tail = max(0.0, trim_tail_seconds)
        usable_duration = max(0.0, duration - trim_head - trim_tail)
        if usable_duration <= 0:
            raise RuntimeError(f"{source.name} trimmed head/tail leaves no usable content.")
        if usable_duration < min_clip_seconds:
            raise RuntimeError(f"{source.name} usable duration is too short.")
        log(
            f"{source.name}: duration {duration:.2f}s, usable {usable_duration:.2f}s, "
            f"trim head {trim_head:g}s, trim tail {trim_tail:g}s"
        )

        part_duration = usable_duration / parts
        for index in range(parts):
            relative_start = index * part_duration
            start = trim_head + relative_start
            length = usable_duration - relative_start if index == parts - 1 else part_duration
            if length < min_clip_seconds:
                continue
            clips.append(
                Clip(
                    id=f"{source.stem}_{index + 1:03d}",
                    source=source,
                    start=start,
                    duration=length,
                    has_audio=has_audio,
                )
            )
    if not clips:
        raise RuntimeError("没有可用片段。请减少切分份数，或降低末尾排除秒数。")
    return clips


def choose_recipes(
    clips: list[Clip],
    output_count: int,
    clips_per_output: int,
    no_reuse: bool,
    rng: random.Random,
) -> list[list[Clip]]:
    if clips_per_output > len(clips):
        raise RuntimeError(f"每个视频需要 {clips_per_output} 个片段，但只有 {len(clips)} 个片段可用。")
    if no_reuse and output_count * clips_per_output > len(clips):
        raise RuntimeError(f"禁止复用时片段不够：需要 {output_count * clips_per_output}，只有 {len(clips)}。")

    recipes: list[list[Clip]] = []
    signatures: set[tuple[str, ...]] = set()
    available = clips[:]
    attempts = 0
    while len(recipes) < output_count and attempts < max(1000, output_count * 300):
        attempts += 1
        if no_reuse:
            recipe = rng.sample(available, clips_per_output)
            for clip in recipe:
                available.remove(clip)
        else:
            recipe = rng.sample(clips, clips_per_output)
        rng.shuffle(recipe)
        signature = tuple(clip.id for clip in recipe)
        if signature in signatures:
            if no_reuse:
                available.extend(recipe)
            continue
        signatures.add(signature)
        recipes.append(recipe)
    if len(recipes) < output_count:
        raise RuntimeError("无法生成足够多的不重复组合。请减少生成数量，或增加源视频/切分份数。")
    return recipes


def extract_clip(clip: Clip, target: Path, width: int, height: int, fps: int, crf: int) -> None:
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={fps},format=yuv420p"
    )
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    command += ["-ss", f"{clip.start:.3f}", "-t", f"{clip.duration:.3f}", "-i", str(clip.source)]
    if clip.has_audio:
        command += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        command += [
            "-f",
            "lavfi",
            "-t",
            f"{clip.duration:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
        ]
    command += [
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(target),
    ]
    run(command)


def concat_clips(segments: list[Path], output: Path) -> None:
    list_file = output.with_suffix(".txt")
    try:
        lines = []
        for path in segments:
            safe = str(path).replace("'", "'\\''")
            lines.append(f"file '{safe}'")
        list_file.write_text("\n".join(lines), encoding="utf-8")
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output)])
    finally:
        list_file.unlink(missing_ok=True)


def concat_story_segments(
    segments: list[Path],
    output: Path,
    fps: int,
    crf: int,
    transition_seconds: float = 0.45,
) -> bool:
    if len(segments) <= 1:
        concat_clips(segments, output)
        return False

    durations = [media_info(path)[0] for path in segments]
    transition = min(float(transition_seconds), min(durations) / 3)
    if transition < 0.15:
        concat_clips(segments, output)
        return False

    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for path in segments:
        command += ["-i", str(path)]

    filters: list[str] = []
    for index in range(len(segments)):
        filters.append(
            f"[{index}:v]fps={fps},settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[vn{index}]"
        )
        filters.append(
            f"[{index}:a]aresample=48000,asetpts=PTS-STARTPTS[an{index}]"
        )

    video_label = "vn0"
    audio_label = "an0"
    timeline = durations[0]
    for index in range(1, len(segments)):
        next_video = f"vn{index}"
        next_audio = f"an{index}"
        out_video = f"v{index}"
        out_audio = f"a{index}"
        offset = max(0.0, timeline - transition)
        filters.append(
            f"[{video_label}][{next_video}]xfade=transition=fade:duration={transition:.3f}:"
            f"offset={offset:.3f},fps={fps},settb=AVTB,format=yuv420p[{out_video}]"
        )
        filters.append(
            f"[{audio_label}][{next_audio}]acrossfade=d={transition:.3f}:c1=tri:c2=tri[{out_audio}]"
        )
        video_label = out_video
        audio_label = out_audio
        timeline += durations[index] - transition

    command += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{video_label}]",
        "-map",
        f"[{audio_label}]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(output),
    ]
    run(command)
    return True


def write_recipe(recipe: list[Clip], output: Path) -> None:
    lines = ["order,source,start_seconds,duration_seconds,clip_id"]
    for index, clip in enumerate(recipe, 1):
        lines.append(f"{index},{clip.source.name},{clip.start:.3f},{clip.duration:.3f},{clip.id}")
    output.write_text("\n".join(lines), encoding="utf-8")


def render_recipes(recipes: list[list[Clip]], out_dir: Path, width: int, height: int, fps: int, crf: int, log=print) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="video_mixer_"))
    try:
        for video_index, recipe in enumerate(recipes, 1):
            log(f"正在生成 mixed_{video_index:03d}.mp4")
            segments = []
            for clip_index, clip in enumerate(recipe, 1):
                segment = temp_root / f"v{video_index:03d}_c{clip_index:03d}_{clip.id}.mp4"
                extract_clip(clip, segment, width, height, fps, crf)
                segments.append(segment)
            output = out_dir / f"mixed_{video_index:03d}.mp4"
            concat_clips(segments, output)
            write_recipe(recipe, out_dir / f"mixed_{video_index:03d}_recipe.csv")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def whole_video_clip(path: Path) -> Clip:
    duration, has_audio = media_info(path)
    return Clip(
        id=path.stem,
        source=path,
        start=0.0,
        duration=duration,
        has_audio=has_audio,
    )


def render_intro_outro_batch(
    base_videos: list[Path],
    intro_video: Path | None,
    outro_video: Path | None,
    out_dir: Path,
    width: int,
    height: int,
    fps: int,
    crf: int,
    log=print,
) -> None:
    if not base_videos:
        raise RuntimeError("No base videos selected.")
    if intro_video is None and outro_video is None:
        raise RuntimeError("Select at least one intro or outro video.")

    out_dir.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="video_mixer_intro_outro_"))
    try:
        shared_segments: list[tuple[str, Path]] = []
        if intro_video is not None:
            intro_segment = temp_root / "shared_intro.mp4"
            extract_clip(whole_video_clip(intro_video), intro_segment, width, height, fps, crf)
            shared_segments.append(("intro", intro_segment))
        if outro_video is not None:
            outro_segment = temp_root / "shared_outro.mp4"
            extract_clip(whole_video_clip(outro_video), outro_segment, width, height, fps, crf)
            shared_segments.append(("outro", outro_segment))

        intro_segment = next((path for name, path in shared_segments if name == "intro"), None)
        outro_segment = next((path for name, path in shared_segments if name == "outro"), None)

        for index, base_video in enumerate(base_videos, 1):
            log(f"Processing {base_video.name} ({index}/{len(base_videos)})")
            base_segment = temp_root / f"base_{index:03d}.mp4"
            extract_clip(whole_video_clip(base_video), base_segment, width, height, fps, crf)

            segments: list[Path] = []
            if intro_segment is not None:
                segments.append(intro_segment)
            segments.append(base_segment)
            if outro_segment is not None:
                segments.append(outro_segment)

            safe_stem = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in base_video.stem).strip()
            output = out_dir / f"{safe_stem or 'video'}_with_intro_outro.mp4"
            concat_clips(segments, output)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def sample_video_frames(
    source: Path,
    frame_dir: Path,
    sample_window_seconds: float = 1.0,
    frames_per_window: int = 1,
    max_frames: int = 60,
    start: float = 0.0,
    window_duration: float | None = None,
) -> list[Path]:
    duration, _ = media_info(source)
    frame_dir.mkdir(parents=True, exist_ok=True)
    if duration <= 0:
        return []
    sample_window_seconds = max(0.1, float(sample_window_seconds))
    frames_per_window = max(1, int(frames_per_window))
    max_frames = max(1, int(max_frames))
    start = max(0.0, min(start, duration))
    end = min(duration, start + window_duration) if window_duration else duration
    if end <= start:
        end = duration
    points = []
    window_start = start
    while window_start < end and len(points) < max_frames:
        if frames_per_window == 1:
            offsets = [0.0]
        else:
            step = sample_window_seconds / frames_per_window
            offsets = [step * i for i in range(frames_per_window)]
        for offset in offsets:
            timestamp = window_start + offset
            if timestamp >= end or len(points) >= max_frames:
                break
            points.append(max(0.0, min(duration - 0.1, timestamp)))
        window_start += sample_window_seconds
    if not points:
        points = [max(0.0, min(duration - 0.1, start))]

    frames = []
    for index, timestamp in enumerate(points, 1):
        target = frame_dir / f"frame_{index:02d}.jpg"
        run([
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(target),
        ])
        if target.exists():
            frames.append(target)
    return frames


def call_openai_compatible_vision(
    source: Path,
    duration: float,
    target_seconds: float,
    previous_summary: str,
    ai_config: dict,
    frame_dir: Path,
    analysis_start: float = 0.0,
    analysis_duration: float | None = None,
    section_name: str = "full",
    story_context: str = "",
) -> tuple[dict | None, list[str]]:
    diagnostics: list[str] = []
    if not ai_config.get("enabled"):
        return None, diagnostics
    api_key = ai_config.get("api_key", "").strip()
    model = ai_config.get("model", "").strip()
    api_base = ai_config.get("api_base", "").strip().rstrip("/")
    if not api_key or not model or not api_base:
        diagnostics.append("AI skipped: api_base/api_key/model is incomplete.")
        return None, diagnostics
    analysis_start = max(0.0, min(float(analysis_start), duration))
    analysis_end = min(duration, analysis_start + analysis_duration) if analysis_duration else duration
    if analysis_end <= analysis_start:
        analysis_end = duration

    frames = sample_video_frames(
        source,
        frame_dir,
        float(ai_config.get("sample_window_seconds", 1.0) or 1.0),
        int(ai_config.get("frames_per_window", 1) or 1),
        int(ai_config.get("max_frames", 60) or 60),
        analysis_start,
        analysis_end - analysis_start,
    )
    diagnostics.append(
        f"AI frames sampled: {len(frames)}; every "
        f"{ai_config.get('sample_window_seconds', 1.0)}s take "
        f"{ai_config.get('frames_per_window', 1)} frame(s)"
    )
    diagnostics.append(f"AI section: {section_name}, range {analysis_start:.2f}s-{analysis_end:.2f}s")
    for frame in frames:
        diagnostics.append(f"  frame: {frame.name}")
    image_items = []
    for frame in frames:
        encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
        image_items.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
        })

    prompt = (
        "你是短剧剪辑助手。请根据这些按时间顺序抽取的画面，为当前源视频选择一个连续精彩片段，"
        "要求剧情连贯、避免重复上一集内容、适合作为独立一集。"
        f"\n视频文件：{source.name}"
        f"\n视频总时长：{duration:.2f} 秒"
        f"\n目标成片时长：{target_seconds:.2f} 秒"
        f"\n上一集内容摘要：{previous_summary or '无'}"
        "\n请只返回 JSON，不要返回 Markdown。格式："
        '{"start": 秒数, "duration": 秒数, "summary": "本集摘要", '
        '"continuity_note": "与上一集衔接说明", "censor_mode": "none|female|male|both"}'
    )
    story_rules = (
        f"\nAnalysis section: {section_name}, only choose inside {analysis_start:.2f}s to {analysis_end:.2f}s. "
        f"\nOverall story context: {story_context or 'none'} "
        "\nEditing constraints: return exactly one continuous time range from the source video. "
        "Return absolute seconds in the original source video, not relative seconds inside the section. "
        "Keep only the core main plot. Remove unnecessary transitions, side plots, establishing shots, repeated dialogue, and filler. "
        "Prefer moments that advance the story, reveal conflict, or complete an important beat. "
        "The selected segment must stay in chronological order; never place later events before earlier events. "
        "Choose natural shot/action/dialogue boundaries, and avoid ending in the middle of a spoken sentence."
    )
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt + story_rules}] + image_items,
            }
        ],
        "temperature": float(ai_config.get("temperature", 0.2) or 0.2),
    }
    url = api_base
    if not url.endswith("/chat/completions"):
        url = f"{url}/chat/completions"
    diagnostics.append(f"AI endpoint: {url}")
    diagnostics.append(f"AI model: {model}")
    retry_count = max(0, int(ai_config.get("retry_count", 2) or 0))
    retry_delay = max(0.0, float(ai_config.get("retry_delay", 8) or 0))
    timeout = int(ai_config.get("timeout", 90) or 90)
    for attempt in range(retry_count + 1):
        diagnostics.append(f"AI request attempt: {attempt + 1}/{retry_count + 1}")
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            content = payload["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
            text = str(content).strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            diagnostics.append(f"AI raw response: {text}")
            parsed = json.loads(text)
            start = max(analysis_start, float(parsed.get("start", analysis_start)))
            length = max(1.0, float(parsed.get("duration", target_seconds)))
            if start >= analysis_end:
                start = max(analysis_start, analysis_end - min(length, analysis_end - analysis_start))
            if start + length > analysis_end:
                length = max(0.5, analysis_end - start)
            parsed["start"] = start
            parsed["duration"] = min(length, duration)
            diagnostics.append(
                f"AI parsed: start={parsed['start']:.2f}s, duration={parsed['duration']:.2f}s, "
                f"censor={parsed.get('censor_mode', 'none')}"
            )
            return parsed, diagnostics
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace") if hasattr(error, "read") else str(error)
            diagnostics.append(f"AI HTTP error: {error.code} {detail}")
            if error.code in TRANSIENT_AI_HTTP_CODES and attempt < retry_count:
                wait_seconds = retry_delay * (attempt + 1)
                diagnostics.append(f"AI transient error; retrying in {wait_seconds:g}s")
                time.sleep(wait_seconds)
                continue
            return None, diagnostics
        except (urllib.error.URLError, TimeoutError) as error:
            diagnostics.append(f"AI network error: {type(error).__name__}: {error}")
            if attempt < retry_count:
                wait_seconds = retry_delay * (attempt + 1)
                diagnostics.append(f"AI network retrying in {wait_seconds:g}s")
                time.sleep(wait_seconds)
                continue
            return None, diagnostics
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            diagnostics.append(f"AI failed: {type(error).__name__}: {error}")
            return None, diagnostics
    return None, diagnostics


def call_censor_vision(
    source: Path,
    start: float,
    duration: float,
    censor_config: dict,
    frame_dir: Path,
) -> tuple[list[dict], list[str]]:
    diagnostics: list[str] = []
    if not censor_config.get("enabled"):
        return [], diagnostics
    api_key = censor_config.get("api_key", "").strip()
    model = censor_config.get("model", "").strip()
    api_base = censor_config.get("api_base", "").strip().rstrip("/")
    if not api_key or not model or not api_base:
        raise RuntimeError("Censor AI config is incomplete.")

    frames = sample_video_frames(
        source,
        frame_dir,
        float(censor_config.get("sample_window_seconds", 1.0) or 1.0),
        int(censor_config.get("frames_per_window", 1) or 1),
        int(censor_config.get("max_frames", 40) or 40),
        start,
        duration,
    )
    diagnostics.append(f"Censor AI frames sampled: {len(frames)}")
    image_items = []
    for frame in frames:
        diagnostics.append(f"  censor frame: {frame.name}")
        encoded = base64.b64encode(frame.read_bytes()).decode("ascii")
        image_items.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
        })

    prompt = (
        "你是视频安全打码助手。请根据这些画面判断是否存在需要模糊处理的女性露沟或男性露胸区域。"
        "只返回 JSON，不要 Markdown。格式："
        '{"boxes":[{"x":0.1,"y":0.2,"w":0.3,"h":0.2,"reason":"说明"}]}。'
        "坐标为 0-1 的归一化比例，尽量只覆盖需要模糊的位置；没有则返回 {\"boxes\":[]}。"
    )
    censor_rules = (
        "\nFinal-video censoring rules: analyze these frames as samples from the final generated video. "
        "Return every normalized region that should be blurred for exposed chest or cleavage. "
        "When unsure, prefer a slightly larger box so the entire exposed chest area is blurred."
    )
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt + censor_rules}] + image_items}],
        "temperature": float(censor_config.get("temperature", 0.1) or 0.1),
    }
    url = api_base
    if not url.endswith("/chat/completions"):
        url = f"{url}/chat/completions"
    diagnostics.append(f"Censor AI endpoint: {url}")
    diagnostics.append(f"Censor AI model: {model}")
    retry_count = max(0, int(censor_config.get("retry_count", 2) or 0))
    retry_delay = max(0.0, float(censor_config.get("retry_delay", 8) or 0))
    timeout = int(censor_config.get("timeout", 90) or 90)
    for attempt in range(retry_count + 1):
        diagnostics.append(f"Censor AI request attempt: {attempt + 1}/{retry_count + 1}")
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            content = payload["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
            text = str(content).strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            diagnostics.append(f"Censor AI raw response: {text}")
            parsed = json.loads(text)
            boxes = []
            for item in parsed.get("boxes", []):
                x = max(0.0, min(1.0, float(item.get("x", 0))))
                y = max(0.0, min(1.0, float(item.get("y", 0))))
                w = max(0.0, min(1.0 - x, float(item.get("w", 0))))
                h = max(0.0, min(1.0 - y, float(item.get("h", 0))))
                if w > 0.01 and h > 0.01:
                    boxes.append({"x": x, "y": y, "w": w, "h": h, "reason": str(item.get("reason", ""))})
            diagnostics.append(f"Censor AI boxes: {len(boxes)}")
            return boxes, diagnostics
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace") if hasattr(error, "read") else str(error)
            diagnostics.append(f"Censor AI HTTP error: {error.code} {detail}")
            if error.code in TRANSIENT_AI_HTTP_CODES and attempt < retry_count:
                wait_seconds = retry_delay * (attempt + 1)
                diagnostics.append(f"Censor AI transient error; retrying in {wait_seconds:g}s")
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(f"Censor AI HTTP error: {error.code} {detail}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            diagnostics.append(f"Censor AI network error: {type(error).__name__}: {error}")
            if attempt < retry_count:
                wait_seconds = retry_delay * (attempt + 1)
                diagnostics.append(f"Censor AI network retrying in {wait_seconds:g}s")
                time.sleep(wait_seconds)
                continue
            raise RuntimeError(f"Censor AI failed: {type(error).__name__}: {error}") from error
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            diagnostics.append(f"Censor AI failed: {type(error).__name__}: {error}")
            raise RuntimeError(f"Censor AI failed: {type(error).__name__}: {error}") from error
    return [], diagnostics


def detect_scene_changes(
    source: Path,
    start: float,
    end: float,
    threshold: float = 0.32,
) -> list[float]:
    scan_start = max(0.0, float(start))
    scan_end = max(scan_start + 0.5, float(end))
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-ss",
        f"{scan_start:.3f}",
        "-t",
        f"{scan_end - scan_start:.3f}",
        "-i",
        str(source),
        "-vf",
        f"select='gt(scene,{threshold})',showinfo",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **startup_options(),
    )
    changes: list[float] = []
    for match in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", result.stderr or ""):
        value = float(match.group(1))
        timestamp = scan_start + value if value < scan_start - 0.5 else value
        if scan_start <= timestamp <= scan_end:
            changes.append(timestamp)
    return sorted(set(round(item, 3) for item in changes))


def detect_silence_starts(
    source: Path,
    start: float,
    duration: float,
    noise: str = "-35dB",
    min_silence: float = 0.35,
) -> list[float]:
    scan_start = max(0.0, float(start))
    scan_duration = max(0.2, float(duration))
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-ss",
        f"{scan_start:.3f}",
        "-t",
        f"{scan_duration:.3f}",
        "-i",
        str(source),
        "-af",
        f"silencedetect=noise={noise}:d={min_silence:g}",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(
        command,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **startup_options(),
    )
    silences: list[float] = []
    for match in re.finditer(r"silence_start:\s*([0-9]+(?:\.[0-9]+)?)", result.stderr or ""):
        value = float(match.group(1))
        timestamp = scan_start + value if value < scan_start - 0.5 else value
        if scan_start <= timestamp <= scan_start + scan_duration:
            silences.append(timestamp)
    return sorted(set(round(item, 3) for item in silences))


def refine_story_segment(
    source: Path,
    start: float,
    length: float,
    total_duration: float,
    target_seconds: float,
) -> tuple[float, float, list[str]]:
    notes: list[str] = []
    original_start = max(0.0, min(float(start), total_duration))
    original_end = max(original_start + 0.5, min(total_duration, original_start + float(length)))
    scan_start = max(0.0, original_start - 2.0)
    scan_end = min(total_duration, original_end + 2.0)
    changes = detect_scene_changes(source, scan_start, scan_end)
    if changes:
        notes.append("Scene changes near AI range: " + ", ".join(f"{item:.2f}s" for item in changes[:12]))
    else:
        notes.append("Scene changes near AI range: none detected")

    adjusted_start = original_start
    adjusted_end = original_end
    min_length = min(max(3.0, target_seconds * 0.45), max(3.0, original_end - original_start))
    head_guard = min(1.0, max(0.35, (original_end - original_start) * 0.04))
    tail_guard = min(2.0, max(0.8, (original_end - original_start) * 0.08))

    head_cuts = [cut for cut in changes if adjusted_start < cut < adjusted_start + head_guard]
    if head_cuts:
        candidate = head_cuts[-1] + 0.04
        if adjusted_end - candidate >= min_length:
            notes.append(f"Adjusted start from {adjusted_start:.2f}s to {candidate:.2f}s to avoid a partial opening shot")
            adjusted_start = candidate

    tail_cuts = [cut for cut in changes if adjusted_end - tail_guard < cut < adjusted_end]
    if tail_cuts:
        candidate = tail_cuts[0] - 0.04
        if candidate - adjusted_start >= min_length:
            notes.append(f"Adjusted end from {adjusted_end:.2f}s to {candidate:.2f}s to remove a stray final shot")
            adjusted_end = candidate

    adjusted_start = max(0.0, min(adjusted_start, total_duration - 0.5))
    adjusted_end = max(adjusted_start + 0.5, min(adjusted_end, total_duration))
    return adjusted_start, adjusted_end - adjusted_start, notes


def extend_segment_for_dialogue(
    source: Path,
    start: float,
    length: float,
    total_duration: float,
    section_end: float | None = None,
    max_extension: float = 4.5,
) -> tuple[float, list[str]]:
    notes: list[str] = []
    _, has_audio = media_info(source)
    current_end = max(0.0, min(total_duration, start + length))
    limit = min(total_duration, section_end if section_end is not None else total_duration, current_end + max(0.5, float(max_extension)))
    if limit <= current_end + 0.2:
        return length, notes

    scene_changes = detect_scene_changes(source, current_end, limit, threshold=0.30)
    if scene_changes:
        limit = min(limit, max(current_end + 0.35, scene_changes[0] - 0.05))
        notes.append(f"Dialogue tail limited by next scene change at {scene_changes[0]:.2f}s")

    if not has_audio:
        extension = min(1.2, max(0.0, limit - current_end))
        if extension > 0.05:
            notes.append(f"Extended tail by {extension:.2f}s because source has no readable audio track")
        return length + extension, notes

    scan_duration = max(0.2, limit - current_end)
    silences = detect_silence_starts(source, current_end, scan_duration)
    usable_silences = [item for item in silences if item >= current_end + 0.35]
    if usable_silences:
        new_end = min(limit, usable_silences[0] + 0.18)
        extension = max(0.0, new_end - current_end)
        if extension > 0.05:
            notes.append(f"Extended tail by {extension:.2f}s to let dialogue reach a silence point")
        return length + extension, notes

    extension = min(2.0, max(0.0, limit - current_end))
    if extension > 0.05:
        notes.append(f"Extended tail by {extension:.2f}s; no clear silence point detected")
    return length + extension, notes


def extract_story_clip(
    source: Path,
    target: Path,
    start: float,
    duration: float,
    width: int,
    height: int,
    fps: int,
    crf: int,
    censor_mode: str,
    censor_boxes: list[dict] | None = None,
) -> None:
    _, has_audio = media_info(source)
    base_vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={fps},format=yuv420p"
    )
    blur_filters: list[str] = []
    for box in censor_boxes or []:
        x = int(width * float(box.get("x", 0)))
        y = int(height * float(box.get("y", 0)))
        w = max(8, int(width * float(box.get("w", 0))))
        h = max(8, int(height * float(box.get("h", 0))))
        blur_filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}:show=0")
    vf = ",".join([base_vf] + blur_filters)

    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    command += ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source)]
    if has_audio:
        command += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        command += [
            "-f",
            "lavfi",
            "-t",
            f"{duration:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
        ]
    command += [
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(target),
    ]
    run(command)


def apply_final_censor(
    video_path: Path,
    width: int,
    height: int,
    fps: int,
    crf: int,
    boxes: list[dict],
) -> None:
    if not boxes:
        return
    duration, _ = media_info(video_path)
    temp_target = video_path.with_name(f"{video_path.stem}_censored_tmp{video_path.suffix}")
    try:
        extract_story_clip(video_path, temp_target, 0.0, duration, width, height, fps, crf, "both", boxes)
        temp_target.replace(video_path)
    finally:
        temp_target.unlink(missing_ok=True)


def apply_final_fade(
    video_path: Path,
    crf: int,
    fade_seconds: float = 1.25,
) -> None:
    duration, has_audio = media_info(video_path)
    if duration <= 0.5:
        return
    fade = min(max(0.35, float(fade_seconds)), max(0.35, duration / 2))
    start = max(0.0, duration - fade)
    temp_target = video_path.with_name(f"{video_path.stem}_fade_tmp{video_path.suffix}")
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fade=t=out:st={start:.3f}:d={fade:.3f},format=yuv420p",
    ]
    if has_audio:
        command += ["-af", f"afade=t=out:st={start:.3f}:d={fade:.3f}"]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(temp_target),
    ]
    try:
        run(command)
        temp_target.replace(video_path)
    finally:
        temp_target.unlink(missing_ok=True)


def render_story_sequence(
    source_videos: list[Path],
    out_dir: Path,
    target_seconds: float,
    width: int,
    height: int,
    fps: int,
    crf: int,
    censor_mode: str,
    memory_path: Path | None = None,
    ai_config: dict | None = None,
    censor_config: dict | None = None,
    log=print,
) -> None:
    if not source_videos:
        raise RuntimeError("No source videos selected.")
    if target_seconds <= 0:
        raise RuntimeError("Target duration must be greater than 0.")
    if not ai_config or not ai_config.get("enabled"):
        raise RuntimeError("AI analysis is required for story editing. Enable AI and complete model settings.")

    out_dir.mkdir(parents=True, exist_ok=True)
    sorted_sources = sorted(source_videos, key=lambda item: item.name.lower())
    durations = []
    for source in sorted_sources:
        duration, _ = media_info(source)
        durations.append(duration)
    total_source_duration = sum(durations)
    if total_source_duration <= 0:
        raise RuntimeError("Could not read source video duration.")

    log("Story sequence order:")
    for index, source in enumerate(sorted_sources, 1):
        log(f"  {index}. {source.name} ({durations[index - 1]:.2f}s)")

    memory = {"episodes": []}
    if memory_path and memory_path.exists():
        try:
            memory = json.loads(memory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            memory = {"episodes": []}
    previous_summary = str(memory.get("summary", ""))
    selected_entries: list[dict] = []
    segment_files: list[Path] = []
    summaries: list[str] = []
    continuity_notes: list[str] = []
    episode_censor = censor_mode
    temp_root = Path(tempfile.mkdtemp(prefix="story_sequence_frames_"))
    try:
        for index, (source, duration) in enumerate(zip(sorted_sources, durations), 1):
            share = duration / total_source_duration
            clip_target = min(duration, max(1.0, target_seconds * share))
            if target_seconds >= total_source_duration:
                clip_target = duration
            story_context = (
                f"These {len(sorted_sources)} videos are one continuous story sorted by filename. "
                f"Current file is {index}/{len(sorted_sources)}. "
                f"Final output target duration is {target_seconds:.2f}s. "
                f"Current file should contribute about {clip_target:.2f}s. "
                f"Keep plot continuity with previous and next files; do not select an ending-only spoiler before setup."
            )
            log(f"Sequence AI {index}/{len(sorted_sources)}: {source.name}, target {clip_target:.2f}s")
            ai_result, ai_logs = call_openai_compatible_vision(
                source,
                duration,
                clip_target,
                previous_summary,
                ai_config or {},
                temp_root / f"sequence_{index:03d}",
                0.0,
                duration,
                f"sequence {index}/{len(sorted_sources)}",
                story_context,
            )
            for line in ai_logs:
                log(line)
            if not ai_result:
                raise RuntimeError(f"AI analysis failed for {source.name}. Stop processing.")

            start = float(ai_result["start"])
            length = float(ai_result["duration"])
            section_censor = str(ai_result.get("censor_mode", censor_mode))
            if section_censor in {"female", "male", "both"}:
                episode_censor = section_censor if episode_censor == "none" else "both"
            summary = str(ai_result.get("summary", ""))
            continuity = str(ai_result.get("continuity_note", ""))
            summaries.append(summary)
            continuity_notes.append(continuity)
            log(f"AI selected sequence part {index}: start {start:.2f}s, duration {length:.2f}s")
            log(f"AI summary: {summary or '(empty)'}")
            log(f"AI continuity: {continuity or '(empty)'}")

            refined_start, refined_length, refine_logs = refine_story_segment(
                source,
                start,
                length,
                duration,
                clip_target,
            )
            for line in refine_logs:
                log(line)
            dialogue_length, dialogue_logs = extend_segment_for_dialogue(
                source,
                refined_start,
                refined_length,
                duration,
                duration,
                10.0 if index == len(sorted_sources) else 4.5,
            )
            for line in dialogue_logs:
                log(line)
            if abs(dialogue_length - refined_length) > 0.01:
                log(
                    f"Dialogue tail adjusted: start {refined_start:.2f}s, "
                    f"duration {dialogue_length:.2f}s"
                )
            refined_length = dialogue_length

            segment_file = temp_root / f"sequence_segment_{index:03d}.mp4"
            extract_story_clip(
                source,
                segment_file,
                refined_start,
                refined_length,
                width,
                height,
                fps,
                crf,
                section_censor if section_censor in {"none", "female", "male", "both"} else censor_mode,
                [],
            )
            segment_files.append(segment_file)
            selected_entries.append({
                "order": index,
                "source": source.name,
                "start": round(refined_start, 3),
                "end": round(refined_start + refined_length, 3),
                "duration": round(refined_length, 3),
                "summary": summary,
                "continuity_note": continuity,
            })
            previous_summary = " / ".join(item for item in summaries if item)[-2000:]

        output = out_dir / "story_sequence.mp4"
        if concat_story_segments(segment_files, output, fps, crf):
            log("Story sequence joined with soft video/audio crossfade transitions")
        else:
            log("Story sequence joined directly")

        if censor_config and censor_config.get("enabled"):
            output_duration, _ = media_info(output)
            log(f"Final censor scan: {output.name}, duration {output_duration:.2f}s")
            censor_boxes, censor_logs = call_censor_vision(
                output,
                0.0,
                output_duration,
                censor_config,
                temp_root / "sequence_final_censor",
            )
            for line in censor_logs:
                log(line)
            for box_index, box in enumerate(censor_boxes, 1):
                log(
                    f"Final censor box {box_index}: x={box['x']:.3f}, y={box['y']:.3f}, "
                    f"w={box['w']:.3f}, h={box['h']:.3f}, reason={box.get('reason','')}"
                )
            if censor_boxes:
                apply_final_censor(output, width, height, fps, crf, censor_boxes)
                log(f"Final censor applied: {len(censor_boxes)} blur box(es)")
            else:
                log("Final censor applied: no exposed chest area detected")
        apply_final_fade(output, crf)
        log("Final fade applied: video and audio fade out together")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    final_summary = " / ".join(item for item in summaries if item)
    memory["episodes"] = selected_entries
    memory["summary"] = final_summary
    target_memory = memory_path or (out_dir / "story_memory.json")
    target_memory.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["order,source,start_seconds,end_seconds,duration_seconds"]
    for item in selected_entries:
        lines.append(f"{item['order']},{item['source']},{item['start']},{item['end']},{item['duration']}")
    (out_dir / "story_plan.csv").write_text("\n".join(lines), encoding="utf-8")
    log(f"Final story sequence: {len(selected_entries)} ordered source segment(s)")
    log(f"Final story summary: {final_summary or '(empty)'}")
