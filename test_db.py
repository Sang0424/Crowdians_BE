import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.archive import ArchivePost, ArchiveAnswer
from beanie import init_beanie, PydanticObjectId

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    # need to load from env or guess database name, probably "crowdians" or similar
    # wait, the app probably has a config. Let's just import the init from app.db.mongodb
    from app.core.config import settings
    from app.db.mongodb import init_db
    await init_db()
    
    post_id = "69c0bf76e43f64146cc2f35b"
    try:
        post = await ArchivePost.get(PydanticObjectId(post_id))
        print("Post found:", post.title if post else None)
    except Exception as e:
        print("Error getting post:", e)
        
    try:
        answers = await ArchiveAnswer.find(ArchiveAnswer.post_id == post_id).to_list()
        print("Answers found:", len(answers))
    except Exception as e:
        print("Error getting answers:", e)

asyncio.run(main())
