import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.models.archive import ArchivePost, ArchiveAnswer
from app.models.academy import KnowledgeCard
from beanie import init_beanie

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    await init_beanie(database=db, document_models=[ArchivePost, ArchiveAnswer, KnowledgeCard])
    
    invalid_keywords = ["유효하지 않는", "유효하지 않은", "Invalid question", "無効な質問"]
    
    # query to find posts
    query = {"$or": [{"title": {"$regex": kw, "$options": "i"}} for kw in invalid_keywords]}
    posts = await ArchivePost.find(query).to_list()
    count = 0
    for p in posts:
        print(f"Deleting {p.id}: {p.title}")
        # cascading deletes
        await ArchiveAnswer.find(ArchiveAnswer.post_id == str(p.id)).delete()
        await KnowledgeCard.find(KnowledgeCard.linked_post_id == str(p.id)).delete()
        await p.delete()
        count += 1
    print(f"Deleted {count} posts.")

if __name__ == "__main__":
    asyncio.run(main())
