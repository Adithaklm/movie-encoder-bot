import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

from aiohttp import web
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from config import *
from database import init_db, upsert_user, create_job, update_job, get_settings, update_settings, reset_settings
from encoder import encode_file, fmt_bytes, fmt_time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("movie-encoder")
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

BOT_SESSION_STRING = os.environ.get("BOT_SESSION_STRING", "").strip()
if BOT_SESSION_STRING:
    bot = TelegramClient(StringSession(BOT_SESSION_STRING), API_ID, API_HASH)
else:
    bot = TelegramClient("bot", API_ID, API_HASH)

user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) if SESSION_STRING else None


def allowed(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


def settings_text(s):
    return (
        "⚙️ **FFmpeg Settings**\n\n"
        f"🎞️ Video codec: `{s['video_codec']}`\n🎚️ CRF: `{s['crf']}`\n⚡ Preset: `{s['preset']}`\n"
        f"📊 Video bitrate: `{s['video_bitrate'] or 'Auto (CRF)'}`\n🖥️ Pixel format: `{s['pixel_format']}`\n\n"
        f"🔊 Audio codec: `{s['audio_codec']}`\n🎵 Audio bitrate: `{s['audio_bitrate']}`\n🔈 Channels: `{s['audio_channels'] or 'Original'}`\n\n"
        f"🎨 Video filter: `{s['video_filter'] or 'None'}`\n📦 Output: `{s['output_format']}`\n🛠️ Extra args: `{s['extra_args'] or 'None'}`"
    )


SETTINGS_BUTTONS = [
    [Button.inline("🎞️ Video Settings", b"set:video"), Button.inline("🔊 Audio Settings", b"set:audio")],
    [Button.inline("📦 Output Settings", b"set:output"), Button.inline("🛠️ Advanced", b"set:advanced")],
    [Button.inline("🔄 Reset Defaults", b"set:reset")],
]


@bot.on(events.NewMessage(pattern=r"^/settings$"))
async def settings_command(event):
    if not allowed(event.sender_id):
        return await event.reply("❌ You are not authorized.")
    await event.reply(settings_text(await get_settings(event.sender_id)), buttons=SETTINGS_BUTTONS)


@bot.on(events.CallbackQuery(pattern=b"set:"))
async def settings_menu(event):
    if not allowed(event.sender_id):
        return await event.answer("Not authorized", alert=True)
    action = event.data.decode().split(":", 1)[1]
    s = await get_settings(event.sender_id)
    if action == "reset":
        await reset_settings(event.sender_id)
        return await event.edit(settings_text(await get_settings(event.sender_id)), buttons=SETTINGS_BUTTONS)
    if action == "video":
        text = "🎞️ **Video Settings**\n\nChoose an option to change:"
        buttons = [
            [Button.inline(f"Codec: {s['video_codec']}", b"edit:video_codec"), Button.inline(f"CRF: {s['crf']}", b"edit:crf")],
            [Button.inline(f"Preset: {s['preset']}", b"edit:preset"), Button.inline(f"Bitrate: {s['video_bitrate'] or 'Auto'}", b"edit:video_bitrate")],
            [Button.inline(f"Pixel: {s['pixel_format']}", b"edit:pixel_format")],
            [Button.inline("⬅️ Back", b"back:main")],
        ]
    elif action == "audio":
        text = "🔊 **Audio Settings**\n\nChoose an option to change:"
        buttons = [
            [Button.inline(f"Codec: {s['audio_codec']}", b"edit:audio_codec"), Button.inline(f"Bitrate: {s['audio_bitrate']}", b"edit:audio_bitrate")],
            [Button.inline(f"Channels: {s['audio_channels'] or 'Original'}", b"edit:audio_channels")],
            [Button.inline("⬅️ Back", b"back:main")],
        ]
    elif action == "output":
        text = "📦 **Output Settings**\n\nChoose an option to change:"
        buttons = [[Button.inline(f"Format: {s['output_format']}", b"edit:output_format")], [Button.inline("⬅️ Back", b"back:main")]]
    else:
        text = "🛠️ **Advanced FFmpeg**\n\nExtra arguments are appended to the FFmpeg command.\n\nCurrent:\n`" + (s['extra_args'] or "None") + "`"
        buttons = [
            [Button.inline("✏️ Change Extra Args", b"edit:extra_args")],
            [Button.inline("🎨 Change Video Filter", b"edit:video_filter")],
            [Button.inline("⬅️ Back", b"back:main")],
        ]
    await event.edit(text, buttons=buttons)


@bot.on(events.CallbackQuery(pattern=b"back:main"))
async def settings_back(event):
    if not allowed(event.sender_id):
        return await event.answer("Not authorized", alert=True)
    await event.edit(settings_text(await get_settings(event.sender_id)), buttons=SETTINGS_BUTTONS)


EDIT_LABELS = {
    "video_codec": "video codec (example: libx264, libx265, libsvtav1)",
    "crf": "CRF (0-51)",
    "preset": "preset (ultrafast to veryslow)",
    "video_bitrate": "video bitrate (example: 2500k). Send auto for CRF.",
    "pixel_format": "pixel format (example: yuv420p)",
    "audio_codec": "audio codec (example: aac, libopus, ac3)",
    "audio_bitrate": "audio bitrate (example: 128k, 192k, 320k)",
    "audio_channels": "audio channels (1, 2, 6) or original",
    "output_format": "output format (mkv or mp4)",
    "video_filter": "video filter (example: scale=-2:720). Send none to disable.",
    "extra_args": "extra FFmpeg arguments. Send none to clear.",
}
pending_edits = {}


@bot.on(events.CallbackQuery(pattern=b"edit:"))
async def edit_setting(event):
    if not allowed(event.sender_id):
        return await event.answer("Not authorized", alert=True)
    key = event.data.decode().split(":", 1)[1]
    if key not in EDIT_LABELS:
        return await event.answer("Unknown setting", alert=True)
    pending_edits[event.sender_id] = key
    await event.answer()
    await event.respond(f"✏️ Send the new value for **{EDIT_LABELS[key]}**.\n\nSend /cancel to stop.")


@bot.on(events.NewMessage(pattern=r"^/cancel$"))
async def cancel(event):
    uid = event.sender_id
    if uid in pending_edits:
        pending_edits.pop(uid, None)
        return await event.reply("❌ Setting change cancelled.")
    await event.reply("❌ Active-job cancellation is not enabled yet. The current FFmpeg job will finish safely.")


@bot.on(events.NewMessage(func=lambda e: e.sender_id in pending_edits and not (e.raw_text or "").startswith("/")))
async def receive_setting(event):
    uid = event.sender_id
    if not allowed(uid):
        pending_edits.pop(uid, None)
        return
    key = pending_edits.pop(uid)
    value = (event.raw_text or "").strip()
    if key == "video_bitrate" and value.lower() == "auto":
        value = ""
    if key in {"video_filter", "extra_args"} and value.lower() == "none":
        value = ""
    if key == "audio_channels" and value.lower() == "original":
        value = ""
    valid = True
    if key == "crf":
        try:
            valid = 0 <= int(value) <= 51
        except ValueError:
            valid = False
    elif key == "output_format":
        valid = value.lower() in {"mkv", "mp4"}
        value = value.lower()
    elif key == "audio_channels":
        try:
            valid = value == "" or 1 <= int(value) <= 16
        except ValueError:
            valid = False
    if not valid:
        return await event.reply("❌ Invalid value. Please try again.")
    await update_settings(uid, **{key: value})
    await event.reply(f"✅ `{key}` updated to `{value or 'Auto/Original/None'}`. Use /settings to review.")


async def progress_message(message, title, done, total, start_time):
    now = time.monotonic()
    elapsed = max(now - start_time, 0.001)
    percent = min(100, done / total * 100) if total else 0
    speed = done / elapsed
    remaining = (total - done) / speed if speed > 0 and total else None
    bar_len = 12
    filled = int(bar_len * percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    try:
        await message.edit(
            f"{title}\n[{bar}] {percent:.1f}%\n"
            f"{fmt_bytes(done)} / {fmt_bytes(total)}\n"
            f"⚡ {fmt_bytes(int(speed))}/s\n"
            f"⏱️ ETA: {fmt_time(remaining)}"
        )
    except Exception:
        pass


async def download_media_with_retry(client, message, output_path, total, progress_callback, retries=3):
    """Use Telethon's normal download_media path and retry cleanly.

    The previous implementation used iter_download() directly. That triggered a
    process exit on Koyeb while Telethon was exporting a borrowed sender for the
    media DC. Standard download_media() handles Telegram's media transfer flow.
    """
    for attempt in range(1, retries + 1):
        try:
            if output_path.exists():
                output_path.unlink()

            last_report = 0.0

            async def callback(current, total_size):
                nonlocal last_report
                now = time.monotonic()
                if now - last_report >= 2 or current >= total_size:
                    last_report = now
                    await progress_callback(current, total_size)

            result = await client.download_media(message, file=str(output_path), progress_callback=callback)
            if not result or not output_path.exists():
                raise RuntimeError("Telegram returned no downloaded file")

            downloaded = output_path.stat().st_size
            if total and downloaded != total:
                raise RuntimeError(f"Downloaded size mismatch: {downloaded}/{total} bytes")
            return
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            log.exception("Telegram media download attempt %s/%s failed", attempt, retries)
            if attempt >= retries:
                raise RuntimeError(
                    f"Telegram download failed after {retries} attempts: {type(exc).__name__}: {exc}"
                ) from exc
            await asyncio.sleep(min(5 * attempt, 15))


@bot.on(events.NewMessage(pattern=r"^/start$"))
async def start(event):
    await upsert_user(event.sender_id, event.sender.username, event.sender.first_name)
    await event.reply("🎬 Movie Encoder Bot\n\nSend me a video/document to encode.\nUse /settings to customize FFmpeg settings.")


@bot.on(events.NewMessage(func=lambda e: bool(e.file)))
async def media(event):
    uid = event.sender_id
    await upsert_user(uid, event.sender.username, event.sender.first_name)
    if not allowed(uid):
        return await event.reply("❌ You are not authorized to use this encoder.")

    size = event.file.size or 0
    if size > 2 * 1024**3:
        return await event.reply("❌ This deployment is configured for files up to about 2 GB.")

    name = event.file.name or f"input_{event.id}.mkv"
    safe = os.path.basename(name).replace("/", "_")
    work = Path(DOWNLOAD_DIR) / str(uid) / str(event.id)
    work.mkdir(parents=True, exist_ok=True)
    inp = work / safe
    settings = await get_settings(uid)
    output_ext = settings.get("output_format", "mkv")
    out = work / f"{Path(safe).stem}.encoded.{output_ext}"
    status = await event.reply("📥 DOWNLOADING\n[░░░░░░░░░░░░] 0.0%")
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

            # The bot client received this message, so use that same client for
            # the media transfer. Do not pass the bot message/file reference to a
            # separate user session.
            await download_media_with_retry(bot, event.message, inp, size, download_progress)
            await progress_message(status, "📥 DOWNLOAD COMPLETE", size, size, download_started)

            await update_job(job_id, status="encoding")
            encode_started = time.monotonic()

            async def encode_progress(percent, current_seconds, duration, remaining):
                elapsed = max(time.monotonic() - encode_started, 0.001)
                speed = current_seconds / elapsed if current_seconds else 0
                filled = int(12 * percent / 100)
                bar = "█" * filled + "░" * (12 - filled)
                try:
                    await status.edit(
                        f"⚙️ ENCODING\n[{bar}] {percent:.1f}%\n"
                        f"🎞️ {fmt_time(current_seconds)} / {fmt_time(duration)}\n"
                        f"⚡ {speed:.2f}x\n⏱️ ETA: {fmt_time(remaining)}"
                    )
                except Exception:
                    pass

            await encode_file(str(inp), str(out), settings, encode_progress)
            output_size = out.stat().st_size
            await update_job(job_id, status="uploading", output_size=output_size)
            upload_started = time.monotonic()

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
            await status.edit(f"❌ Encoding failed\n{type(exc).__name__}: {str(exc)[:450]}")
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
    try:
        if BOT_SESSION_STRING:
            await bot.start()
        else:
            await bot.start(bot_token=BOT_TOKEN)
    except FloodWaitError as exc:
        log.error(
            "Telegram bot authorization is rate-limited for %s seconds. "
            "Configure BOT_SESSION_STRING after the cooldown to prevent repeated authorization on Koyeb restarts.",
            exc.seconds,
        )
        await health_runner.cleanup()
        raise

    if user_client is not None:
        await user_client.start()

    log.info("Bot started")
    try:
        await bot.run_until_disconnected()
    finally:
        if user_client is not None:
            await user_client.disconnect()
        await bot.disconnect()
        await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
