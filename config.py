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
VIDEO_CODEC = os.environ.get("VIDEO_CODEC", "libx264")
AUDIO_CODEC = os.environ.get("AUDIO_CODEC", "aac")
CRF = os.environ.get("CRF", "23")
PRESET = os.environ.get("PRESET", "veryfast")
AUDIO_BITRATE = os.environ.get("AUDIO_BITRATE", "128k")
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "1"))
