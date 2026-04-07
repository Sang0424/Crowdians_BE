import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.models.academy import KnowledgeCard

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    await init_beanie(database=db, document_models=[KnowledgeCard])
    
    teach = await KnowledgeCard.find(KnowledgeCard.type == "teach").count()
    vote = await KnowledgeCard.find(KnowledgeCard.type == "vote").count()
    print(f"Teach: {teach}, Vote: {vote}")

if __name__ == "__main__":
    asyncio.run(main())
