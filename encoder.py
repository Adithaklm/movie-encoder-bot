import asyncio
import os
from pathlib import Path
from config import VIDEO_CODEC, AUDIO_CODEC, CRF, PRESET, AUDIO_BITRATE

async def encode_file(input_path: str, output_path: str, progress_callback=None):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", VIDEO_CODEC, "-preset", PRESET, "-crf", CRF,
        "-c:a", AUDIO_CODEC, "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart", output_path,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    while True:
        line = await process.stderr.readline()
        if not line:
            break
        if progress_callback:
            await progress_callback(line.decode(errors="ignore"))
    code = await process.wait()
    if code != 0:
        raise RuntimeError(f"FFmpeg exited with code {code}")
    return Path(output_path)
