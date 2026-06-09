import redis.asyncio as aioredis
from app.core.config import settings

_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
