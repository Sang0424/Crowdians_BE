# scratch/check_db_quests.py
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.db import init_db
from app.models.quest import Quest

async def check():
    await init_db()
    total = await Quest.find_all().count()
    turn_limited = await Quest.find(Quest.quest_type == "turn_limited").count()
    active_tl = await Quest.find(Quest.quest_type == "turn_limited", Quest.status == "active").count()
    
    print(f"Total Quests: {total}")
    print(f"Turn Limited Quests: {turn_limited}")
    print(f"Active Turn Limited Quests: {active_tl}")
    
    if turn_limited > 0:
        first = await Quest.find(Quest.quest_type == "turn_limited").first_or_none()
        if first:
            print(f"Sample Quest: {first.title}, Status: {first.status}, Type: {first.quest_type}")

if __name__ == "__main__":
    asyncio.run(check())
