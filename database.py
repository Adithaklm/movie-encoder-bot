from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DATABASE_NAME

client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=10000)
db = client[DATABASE_NAME]
users = db.users
jobs = db.jobs

DEFAULT_SETTINGS = {
    "video_codec": "libx265",
    "crf": "23",
    "preset": "ultrafast",
    "video_bitrate": "",
    "pixel_format": "yuv420p",
    "audio_codec": "aac",
    "audio_bitrate": "128k",
    "audio_channels": "",
    "video_filter": "",
    "output_format": "mkv",
    "extra_args": "",
}

async def init_db():
    await users.create_index(
        "user_id",
        unique=True,
        name="user_id_unique",
        partialFilterExpression={"user_id": {"$type": "int"}},
    )
    await jobs.create_index([("user_id", 1), ("created_at", -1)])
    await client.admin.command("ping")

async def upsert_user(user_id: int, username: str | None, first_name: str | None):
    await users.update_one(
        {"user_id": user_id},
        {
            "$set": {"username": username, "first_name": first_name},
            "$setOnInsert": {"joined_at": datetime.now(timezone.utc), "settings": DEFAULT_SETTINGS.copy()},
        },
        upsert=True,
    )

async def get_settings(user_id: int):
    doc = await users.find_one({"user_id": user_id}, {"settings": 1})
    settings = DEFAULT_SETTINGS.copy()
    if doc and isinstance(doc.get("settings"), dict):
        settings.update(doc["settings"])
    return settings

async def update_settings(user_id: int, **settings):
    fields = {f"settings.{key}": value for key, value in settings.items()}
    await users.update_one({"user_id": user_id}, {"$set": fields}, upsert=True)

async def reset_settings(user_id: int):
    await users.update_one({"user_id": user_id}, {"$set": {"settings": DEFAULT_SETTINGS.copy()}}, upsert=True)

async def create_job(user_id: int, input_name: str, input_size: int):
    doc = {
        "user_id": user_id,
        "input_name": input_name,
        "input_size": input_size,
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
    }
    result = await jobs.insert_one(doc)
    return result.inserted_id

async def update_job(job_id, **fields):
    await jobs.update_one({"_id": job_id}, {"$set": fields})
