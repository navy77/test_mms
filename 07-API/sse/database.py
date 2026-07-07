import os
import logging
from fastapi import HTTPException, status
import redis

import redis.asyncio as aioredis

logger = logging.getLogger("SSEBackend.Database")

# Global connection pool
_redis_pool = None

def get_redis_client():
    global _redis_pool
    host = os.getenv("REDIS_HOST", "redis").strip().strip("'\"")
    port = int(os.getenv("REDIS_PORT", 6379))
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool(
            host=host,
            port=port,
            decode_responses=True
        )
    return aioredis.Redis(connection_pool=_redis_pool)
