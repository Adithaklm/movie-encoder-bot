from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DATABASE_NAME

client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=10000)
db = client[DATABASE_NAME]
users = db.users
jobs = db.jobs

async def init_db():
    # Partial unique index ignores legacy documents that do not contain user_id.
    # This prevents E11000 duplicate-key errors from old/null records.
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
            "$setOnInsert": {"joined_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )

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
