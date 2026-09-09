# Telegram Movie Encoder Bot

A Python Telegram encoder using Telethon, FFmpeg, MongoDB Atlas, and Docker/Koyeb.

## Features

- Telegram bot account plus a Telegram user MTProto session for cross-DC downloads
- Handles Telegram media up to approximately 2 GB per job
- FFmpeg H.264 encoding by default
- MongoDB job tracking and persistent per-user FFmpeg settings
- Inline `/settings` menu for video, audio, output, and advanced options
- Download, encode, and upload progress with percentage, size, speed, and ETA
- Single-job queue by default to protect a small Koyeb instance
- Automatic temporary-file cleanup

## Important 2 GB disk note

A 2 GB Koyeb disk is tight for a 2 GB input because normal file-based encoding requires the input and output to coexist. This project cleans files aggressively and limits concurrency to 1, but **2 GB disk is not sufficient to guarantee successful 2 GB file encodes**. For reliable 2 GB processing, provision more ephemeral disk or redesign around external object storage/streaming.

## Environment variables

Configure these in Koyeb. **Never commit secrets to GitHub.**

`BOT_TOKEN`: BotFather bot token.

`BOT_SESSION_STRING`: Recommended persistent Telethon bot StringSession. Generate it locally with `generate_bot_session.py`. This prevents repeated bot authorization on Koyeb restarts and helps avoid Telegram `ImportBotAuthorizationRequest` flood waits.

`API_ID` / `API_HASH`: Telegram application credentials from my.telegram.org.

`SESSION_STRING`: Telegram user StringSession used by the encoder to retrieve/download incoming files across Telegram data centers. Generate/store this securely and do not publish it.

`MONGO_URI`: MongoDB Atlas connection string.

`DATABASE_NAME`: MongoDB database name.

`OWNER_ID`: Telegram numeric ID of the owner.

`AUTHORIZED_USERS`: comma-separated numeric Telegram IDs.

## Generate BOT_SESSION_STRING

The repository includes `generate_bot_session.py`. Run it **on your own computer**, not on Koyeb:

```bash
pip install -r requirements.txt
python generate_bot_session.py
```

The script asks for `API_ID`, `API_HASH`, and `BOT_TOKEN`, authenticates the bot, and prints a StringSession. Copy that value into Koyeb as `BOT_SESSION_STRING`.

Do not paste the generated session string into GitHub source code or chat. A session string grants access to the associated Telegram account.

## MongoDB Atlas

Create a cluster, database user, and network access rule. Put the resulting connection URI into Koyeb as `MONGO_URI`. MongoDB stores metadata and settings; movie files remain temporary on the Koyeb instance.

## Koyeb deployment

1. Create a Koyeb App.
2. Choose deployment from GitHub.
3. Select `Adithaklm/movie-encoder-bot` and branch `main`.
4. Let Koyeb build the repository using the `Dockerfile`.
5. Add all required environment variables, especially `BOT_SESSION_STRING` and the user `SESSION_STRING`.
6. Set the service command to the Dockerfile default, or `python bot.py` if Koyeb asks for an override.
7. Start with one instance and one concurrent encoding job.

## Telegram

Create a bot with BotFather and obtain `BOT_TOKEN`. Obtain `API_ID` and `API_HASH` from Telegram's developer portal. Do not publish any token or session string.

## Commands

- `/start` - show usage
- `/settings` - customize persistent FFmpeg settings
- `/cancel` - cancel a pending settings edit / show job cancellation status

Send a video or document to start an encoding job.

## License

Use responsibly and only process content you have the right to process or distribute.
