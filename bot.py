import asyncio
import logging
import os
import shutil
from pathlib import Path

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import *
from database import init_db, upsert_user, create_job, update_job
from encoder import encode_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("movie-encoder")
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

bot = TelegramClient("bot", API_ID, API_HASH)
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) if SESSION_STRING else bot


def allowed(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS

@bot.on(events.NewMessage(pattern=r"^/start$"))
async def start(event):
    await upsert_user(event.sender_id, event.sender.username, event.sender.first_name)
    await event.reply("🎬 Movie Encoder Bot\n\nSend me a video/document and I will encode it with FFmpeg.\nUse /cancel to cancel your current job.")

@bot.on(events.NewMessage(pattern=r"^/cancel$"))
async def cancel(event):
    await event.reply("Cancellation is available for queued jobs; an active FFmpeg process will finish safely before cleanup in this version.")

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
    status = await event.reply("📥 Downloading... 0%")
    job_id = await create_job(uid, safe, size)
    try:
        async with semaphore:
            await update_job(job_id, status="downloading")
            await event.download_media(file=str(inp))
            await status.edit("⚙️ Encoding with FFmpeg...")
            await update_job(job_id, status="encoding")
            await encode_file(str(inp), str(out))
            await update_job(job_id, status="uploading", output_size=out.stat().st_size)
            await status.edit("📤 Uploading encoded file...")
            await bot.send_file(event.chat_id, str(out), caption=f"🎬 {out.name}")
            await update_job(job_id, status="completed")
            await status.delete()
    except Exception as exc:
        log.exception("Job failed")
        await update_job(job_id, status="failed", error=str(exc)[:500])
        await status.edit(f"❌ Encoding failed: {str(exc)[:500]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

async def main():
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    log.info("Bot started")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
