import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.models.archive import ArchivePost
from app.models.academy import KnowledgeCard
from beanie import init_beanie

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]
    await init_beanie(database=db, document_models=[ArchivePost, KnowledgeCard])
    
    post_count = await ArchivePost.count()
    card_count = await KnowledgeCard.count()
    
    ko_cards = await KnowledgeCard.find(KnowledgeCard.locale == "ko").count()
    migrated_cards = await KnowledgeCard.find(KnowledgeCard.is_migrated == True).count()
    
    print(f"ArchivePost count: {post_count}")
    print(f"KnowledgeCard count: {card_count}")
    print(f"KnowledgeCard (ko) count: {ko_cards}")
    print(f"KnowledgeCard (migrated=True) count: {migrated_cards}")

if __name__ == "__main__":
    asyncio.run(main())
