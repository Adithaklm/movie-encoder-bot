import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ.get("SESSION_STRING", "")
MONGO_URI = os.environ["MONGO_URI"]
DATABASE_NAME = os.environ.get("DATABASE_NAME", "movie_encoder")
OWNER_ID = int(os.environ["OWNER_ID"])
AUTHORIZED_USERS = {int(x) for x in os.environ.get("AUTHORIZED_USERS", "").split(",") if x.strip().isdigit()}
AUTHORIZED_USERS.add(OWNER_ID)
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "/tmp/encoder")

# Default FFmpeg settings. Users can override these from the bot's Settings menu.
VIDEO_CODEC = os.environ.get("VIDEO_CODEC", "libx265")
AUDIO_CODEC = os.environ.get("AUDIO_CODEC", "aac")
CRF = os.environ.get("CRF", "23")
PRESET = os.environ.get("PRESET", "ultrafast")
AUDIO_BITRATE = os.environ.get("AUDIO_BITRATE", "128k")
VIDEO_BITRATE = os.environ.get("VIDEO_BITRATE", "")
PIXEL_FORMAT = os.environ.get("PIXEL_FORMAT", "yuv420p")
OUTPUT_FORMAT = os.environ.get("OUTPUT_FORMAT", "mkv")
VIDEO_FILTER = os.environ.get("VIDEO_FILTER", "")
AUDIO_CHANNELS = os.environ.get("AUDIO_CHANNELS", "")
EXTRA_FFMPEG_ARGS = os.environ.get("EXTRA_FFMPEG_ARGS", "")

# Keep only one encode running at a time to reduce RAM pressure on small instances.
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "1"))
