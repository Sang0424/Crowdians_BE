import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.models.academy import KnowledgeCard
from app.models.archive import ArchivePost, ArchiveAnswer
from app.models.user import User
from beanie.operators import NotIn, Or

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    await init_beanie(database=db, document_models=[KnowledgeCard, ArchivePost, ArchiveAnswer, User])
    
    user = await User.find_one({})
    if not user:
        print("No user found")
        return
        
    answered_posts = await ArchiveAnswer.find(ArchiveAnswer.author_id == user.uid).to_list()
    answered_post_ids = [ans.post_id for ans in answered_posts]
    
    my_posts = await ArchivePost.find(ArchivePost.author_id == user.uid).to_list()
    my_post_ids = [str(p.id) for p in my_posts]
    
    excluded_linked_ids = list(set(answered_post_ids + my_post_ids))
    print(f"User UID: {user.uid}, answered: {len(answered_post_ids)}, my_posts: {len(my_post_ids)}, unique excluded: {len(excluded_linked_ids)}")
    
    query_filters = [
        KnowledgeCard.is_migrated == False,
        KnowledgeCard.locale == "ko"
    ]
    
    if excluded_linked_ids:
        query_filters.append(
            Or(
                KnowledgeCard.linked_post_id == None,
                NotIn(KnowledgeCard.linked_post_id, excluded_linked_ids)
            )
        )
        
    c = await KnowledgeCard.find(*query_filters).count()
    print(f"Cards available for user: {c}")

if __name__ == "__main__":
    asyncio.run(main())
