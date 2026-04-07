import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.models.academy import KnowledgeCard
from app.models.archive import ArchivePost

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    await init_beanie(database=db, document_models=[KnowledgeCard, ArchivePost])
    
    posts = await ArchivePost.count()
    cards = await KnowledgeCard.count()
    cards_ko = await KnowledgeCard.find(KnowledgeCard.locale == "ko").count()
    cards_en = await KnowledgeCard.find(KnowledgeCard.locale == "en").count()
    cards_ja = await KnowledgeCard.find(KnowledgeCard.locale == "ja").count()
    
    migrated = await KnowledgeCard.find(KnowledgeCard.is_migrated == True).count()
    print(f"Posts: {posts}, Cards total: {cards}, KO: {cards_ko}, EN: {cards_en}, JA: {cards_ja}, Migrated: {migrated}")

if __name__ == "__main__":
    asyncio.run(main())
