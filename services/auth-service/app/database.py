from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

settings = get_settings()

client = AsyncIOMotorClient(settings.MONGO_URI)
db = client.get_default_database()


async def init_db():
    # Collections and indexes are initialized by init_db.js
    pass


async def get_db():
    yield db
