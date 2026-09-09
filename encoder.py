import asyncio
import re
import time
from pathlib import Path

import imageio_ffmpeg

from config import VIDEO_CODEC, AUDIO_CODEC, CRF, PRESET, AUDIO_BITRATE

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def fmt_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def fmt_time(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


async def get_duration(input_path: str) -> float:
    process = await asyncio.create_subprocess_exec(
        FFMPEG, "-i", input_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    text = stderr.decode(errors="ignore")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def encode_file(input_path: str, output_path: str, progress_callback=None):
    duration = await get_duration(input_path)
    cmd = [
        FFMPEG, "-y", "-i", input_path,
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", VIDEO_CODEC, "-preset", PRESET, "-crf", CRF,
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-progress", "pipe:1", "-nostats", output_path,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    started = time.monotonic()
    last_update = 0.0
    current_seconds = 0.0

    async def drain_stderr():
        while await process.stderr.readline():
            pass

    stderr_task = asyncio.create_task(drain_stderr())
    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode(errors="ignore").strip()
            if text.startswith("out_time="):
                value = text.split("=", 1)[1]
                parts = value.split(":")
                if len(parts) == 3:
                    try:
                        current_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                    except ValueError:
                        pass
            elif text == "progress=end":
                current_seconds = duration

            now = time.monotonic()
            if progress_callback and now - last_update >= 2:
                last_update = now
                percent = min(100, current_seconds / duration * 100) if duration else 0
                elapsed = now - started
                speed = current_seconds / elapsed if elapsed > 0 else 0
                remaining = (duration - current_seconds) / speed if speed > 0 and duration else None
                await progress_callback(percent, current_seconds, duration, remaining)

        await stderr_task
        code = await process.wait()
    finally:
        if not stderr_task.done():
            stderr_task.cancel()

    if code != 0:
        raise RuntimeError(f"FFmpeg exited with code {code}")
    if progress_callback:
        await progress_callback(100, duration, duration, 0)
    return Path(output_path)
