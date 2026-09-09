# Telegram Movie Encoder Bot

A Python Telegram encoder using Telethon, FFmpeg, MongoDB Atlas, and Docker/Koyeb.

## Features

- Telegram Bot API account plus Telethon/MTProto configuration
- Handles Telegram media up to approximately 2 GB per job
- FFmpeg H.264 encoding by default
- MongoDB job tracking
- User authorization
- Single-job queue by default to protect a small Koyeb instance
- Automatic temporary-file cleanup
- Docker image with FFmpeg included

## Important 2 GB disk note

A 2 GB Koyeb disk is tight for a 2 GB input because normal file-based encoding requires the input and output to coexist. This project cleans files aggressively and limits concurrency to 1, but **2 GB disk is not sufficient to guarantee successful 2 GB file encodes**. For reliable 2 GB processing, provision more ephemeral disk or redesign around external object storage/streaming.

## Environment variables

Copy `.env.example` and configure the values in Koyeb. Never commit secrets.

`BOT_TOKEN`: BotFather bot token.

`API_ID` / `API_HASH`: Telegram application credentials from my.telegram.org.

`SESSION_STRING`: Optional Telethon user session string. The current bot can operate with the bot session; use a user session only when your workflow specifically needs user-account MTProto access and comply with Telegram's rules.

`MONGO_URI`: MongoDB Atlas connection string.

`DATABASE_NAME`: MongoDB database name.

`OWNER_ID`: Telegram numeric ID of the owner.

`AUTHORIZED_USERS`: comma-separated numeric Telegram IDs.

## MongoDB Atlas

Create a cluster, database user, and network access rule. Put the resulting connection URI into Koyeb as `MONGO_URI`. MongoDB stores metadata only; movie files remain temporary on the Koyeb instance.

## Koyeb deployment

1. Create a Koyeb App.
2. Choose deployment from GitHub.
3. Select `Adithaklm/movie-encoder-bot` and branch `main`.
4. Let Koyeb build the repository using the `Dockerfile`.
5. Add the environment variables listed above.
6. Set the service command to the Dockerfile default, or `python bot.py` if Koyeb asks for an override.
7. Start with one instance and one concurrent encoding job.

## Telegram

Create a bot with BotFather and obtain `BOT_TOKEN`. Obtain `API_ID` and `API_HASH` from Telegram's developer portal. Do not publish either secret.

## Commands

- `/start` - show usage
- `/cancel` - cancellation notice / queue control

Send a video or document to start an encoding job.

## License

Use responsibly and only process content you have the right to process or distribute.
