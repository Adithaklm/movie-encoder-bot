import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

from aiohttp import web
from telethon import TelegramClient, events

from config import *
from database import init_db, upsert_user, create_job, update_job
from encoder import encode_file, fmt_bytes, fmt_time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("movie-encoder")
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

bot = TelegramClient("bot", API_ID, API_HASH)


def allowed(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


async def progress_message(message, title, done, total, start_time):
    now = time.monotonic()
    elapsed = max(now - start_time, 0.001)
    percent = min(100, done / total * 100) if total else 0
    speed = done / elapsed
    remaining = (total - done) / speed if speed > 0 and total else None
    bar_len = 12
    filled = int(bar_len * percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    text = (
        f"{title}\n"
        f"[{bar}] {percent:.1f}%\n"
        f"{fmt_bytes(done)} / {fmt_bytes(total)}\n"
        f"⚡ {fmt_bytes(int(speed))}/s\n"
        f"⏱️ ETA: {fmt_time(remaining)}"
    )
    try:
        await message.edit(text)
    except Exception:
        pass


@bot.on(events.NewMessage(pattern=r"^/start$"))
async def start(event):
    await upsert_user(event.sender_id, event.sender.username, event.sender.first_name)
    await event.reply(
        "🎬 Movie Encoder Bot\n\n"
        "Send me a video/document and I will encode it with FFmpeg.\n"
        "You will see download, encoding and upload progress."
    )


@bot.on(events.NewMessage(pattern=r"^/cancel$"))
async def cancel(event):
    await event.reply("❌ Active-job cancellation is not enabled yet. The current FFmpeg job will finish safely.")


@bot.on(events.NewMessage(func=lambda e: bool(e.file)))
async def media(event):
    uid = event.sender_id
    await upsert_user(uid, event.sender.username, event.sender.first_name)
    if not allowed(uid):
        await event.reply("❌ You are not authorized to use this encoder.")
        return

    size = event.file.size or 0
    if size > 2 * 1024**3:
        await event.reply("❌ This deployment is configured for files up to about 2 GB.")
        return

    name = event.file.name or f"input_{event.id}.mkv"
    safe = os.path.basename(name).replace("/", "_")
    work = Path(DOWNLOAD_DIR) / str(uid) / str(event.id)
    work.mkdir(parents=True, exist_ok=True)
    inp = work / safe
    stem = Path(safe).stem
    out = work / f"{stem}.encoded.mkv"
    status = await event.reply("📥 Downloading...\n[░░░░░░░░░░░░] 0.0%")
    job_id = await create_job(uid, safe, size)

    try:
        async with semaphore:
            await update_job(job_id, status="downloading")
            download_started = time.monotonic()
            last_download_update = 0.0

            async def download_progress(current, total):
                nonlocal last_download_update
                now = time.monotonic()
                if now - last_download_update < 2 and current < total:
                    return
                last_download_update = now
                await progress_message(status, "📥 DOWNLOADING", current, total, download_started)

            await event.download_media(file=str(inp), progress_callback=download_progress)
            await progress_message(status, "📥 DOWNLOAD COMPLETE", size, size, download_started)

            await update_job(job_id, status="encoding")
            encode_started = time.monotonic()

            async def encode_progress(percent, current_seconds, duration, remaining):
                elapsed = max(time.monotonic() - encode_started, 0.001)
                speed = current_seconds / elapsed if current_seconds > 0 else 0
                text = (
                    f"⚙️ ENCODING\n"
                    f"[{('█' * int(12 * percent / 100)).ljust(12, '░')}] {percent:.1f}%\n"
                    f"🎞️ {fmt_time(current_seconds)} / {fmt_time(duration)}\n"
                    f"⚡ {speed:.2f}x\n"
                    f"⏱️ ETA: {fmt_time(remaining)}"
                )
                try:
                    await status.edit(text)
                except Exception:
                    pass

            await encode_file(str(inp), str(out), encode_progress)
            await update_job(job_id, status="uploading", output_size=out.stat().st_size)

            upload_started = time.monotonic()
            output_size = out.stat().st_size

            async def upload_progress(current, total):
                await progress_message(status, "📤 UPLOADING", current, total, upload_started)

            await bot.send_file(
                event.chat_id,
                str(out),
                caption=f"🎬 {out.name}\n📦 {fmt_bytes(output_size)}",
                progress_callback=upload_progress,
            )
            await update_job(job_id, status="completed")
            await status.edit(f"✅ COMPLETE\n📦 {fmt_bytes(output_size)}")
            await asyncio.sleep(3)
            await status.delete()

    except Exception as exc:
        log.exception("Job failed")
        await update_job(job_id, status="failed", error=str(exc)[:500])
        try:
            await status.edit(f"❌ Encoding failed\n{str(exc)[:500]}")
        except Exception:
            pass
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def health(request):
    return web.json_response({"status": "ok"})


async def start_health_server():
    app = web.Application()
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("Health server running on port %s", port)
    return runner


async def main():
    await init_db()
    health_runner = await start_health_server()
    await bot.start(bot_token=BOT_TOKEN)
    log.info("Bot started")
    try:
        await bot.run_until_disconnected()
    finally:
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
