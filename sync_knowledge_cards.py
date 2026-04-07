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
    
    posts = await ArchivePost.find_all().to_list()
    count = 0
    for p in posts:
        # Check if a card already exists for this post
        card = await KnowledgeCard.find_one(KnowledgeCard.linked_post_id == str(p.id))
        if not card:
            # Determine category string
            cat_str = p.domain_category.value if hasattr(p.domain_category, 'value') else str(p.domain_category)
            
            print(f"Creating card for post {p.id}: {p.title}")
            new_card = KnowledgeCard(
                type="teach",
                question=f"[{cat_str}] {p.title}",
                content=p.content,
                summary=p.summary,
                choices=[],
                correct_answer="",
                priority=100 if p.is_sos else 0,
                locale=p.locale,
                linked_post_id=str(p.id)
            )
            await new_card.insert()
            count += 1
    print(f"Created {count} missing cards.")

if __name__ == "__main__":
    asyncio.run(main())
