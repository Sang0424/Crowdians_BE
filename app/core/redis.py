# app/core/redis.py

import redis.asyncio as aioredis

from app.core.config import settings

# 전역 Redis 클라이언트 (lifespan에서 초기화/종료)
redis_client: aioredis.Redis | None = None


async def init_redis() -> None:
    """앱 시작 시 Redis 연결"""
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis() -> None:
    """앱 종료 시 Redis 연결 해제"""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None


def get_redis() -> aioredis.Redis:
    """Redis 클라이언트 반환 (DI용)"""
    if redis_client is None:
        raise RuntimeError("Redis가 초기화되지 않았습니다.")
    return redis_client
