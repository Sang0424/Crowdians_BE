import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.db.mongodb import init_db
from app.models.academy import KnowledgeCard

async def cleanup():
    await init_db()
    
    prefixes = ["[함정 답변]:", "[함정 답변]", "[함정 오답]:", "[함정 오답]"]
    
    count = 0
    cards = await KnowledgeCard.find().to_list()
    
    for card in cards:
        modified = False
        
        # 1. choices
        if card.choices:
            new_choices = []
            for choice in card.choices:
                new_choice = choice
                for p in prefixes:
                    if new_choice.startswith(p):
                        new_choice = new_choice[len(p):].strip()
                        modified = True
                new_choices.append(new_choice)
            card.choices = new_choices
            
        # 2. honeymoon_answer (if it refers to the field by another name check model)
        # In academy_service.py, I saw honeypot_answer
        if hasattr(card, "honeypot_answer") and card.honeypot_answer:
            new_honeypot = card.honeypot_answer
            for p in prefixes:
                if new_honeypot.startswith(p):
                    new_honeypot = new_honeypot[len(p):].strip()
                    modified = True
            card.honeypot_answer = new_honeypot
            
        if modified:
            await card.save()
            count += 1
            print(f"Cleaned card {card.id}")
            
    print(f"Total cleaned cards: {count}")

if __name__ == "__main__":
    asyncio.run(cleanup())
