import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.db.mongodb import init_db
from app.models.academy import KnowledgeCard

async def main():
    await init_db()
    
    # 1. Total counts
    all_count = await KnowledgeCard.count()
    print(f"Total KnowledgeCards: {all_count}")
    
    # 2. Locale counts
    locales = ["ko", "en", "ja"]
    for loc in locales:
        count = await KnowledgeCard.find(KnowledgeCard.locale == loc).count()
        unmigrated = await KnowledgeCard.find(KnowledgeCard.locale == loc, KnowledgeCard.is_migrated == False).count()
        print(f"Locale {loc}: {count} total, {unmigrated} unmigrated")
        
    # 3. Sample card
    sample = await KnowledgeCard.find_one()
    if sample:
        print(f"Sample Card: id={sample.id}, locale={sample.locale}, type={sample.type}, is_migrated={sample.is_migrated}")
    else:
        print("No cards found in DB")

if __name__ == "__main__":
    asyncio.run(main())
