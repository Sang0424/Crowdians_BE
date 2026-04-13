from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import json
from datetime import datetime

async def check_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017/")
    db = client.crowdians_db_dev
    collection = db.chat_conversations
    
    # Get last 5 conversations
    docs = await collection.find().sort("createdAt", -1).limit(5).to_list(length=5)
    
    result = []
    for doc in docs:
        # Convert ObjectId and datetime to string for JSON serialization
        doc['_id'] = str(doc['_id'])
        if 'createdAt' in doc:
            doc['createdAt'] = doc['createdAt'].isoformat()
        if 'updatedAt' in doc:
            doc['updatedAt'] = doc['updatedAt'].isoformat()
        if 'messages' in doc:
            # Check message types and content
            for msg in doc['messages']:
                if 'createdAt' in msg and isinstance(msg['createdAt'], datetime):
                    msg['createdAt'] = msg['createdAt'].isoformat()
        result.append(doc)
    
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(check_db())
