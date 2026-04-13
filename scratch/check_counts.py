import asyncio
import os
from app.db import init_db
from app.models.academy import KnowledgeCard
from app.models.archive import ArchivePost

async def count():
    os.environ["APP_ENV"] = "dev"
    await init_db()
    cards_count = await KnowledgeCard.find_all().count()
    posts_count = await ArchivePost.find_all().count()
    print(f"Total KnowledgeCards: {cards_count}")
    print(f"Total ArchivePosts: {posts_count}")
    
    # Check by locale
    for loc in ["ko", "en", "ja"]:
        c = await KnowledgeCard.find(KnowledgeCard.locale == loc).count()
        p = await ArchivePost.find(ArchivePost.locale == loc).count()
        print(f"[{loc}] Cards: {c}, Posts: {p}")

if __name__ == "__main__":
    asyncio.run(count())
