import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.models.archive import ArchivePost

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    await init_beanie(database=db, document_models=[ArchivePost])
    
    for loc in ["ko", "en", "ja", "other"]:
        if loc == "other":
            count = await ArchivePost.find({"locale": {"$nin": ["ko", "en", "ja"]}}).count()
        else:
            count = await ArchivePost.find(ArchivePost.locale == loc).count()
        print(f"ArchivePost locale {loc}: {count}")

if __name__ == "__main__":
    asyncio.run(main())
