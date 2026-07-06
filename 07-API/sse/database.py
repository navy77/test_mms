import os
import logging
from fastapi import HTTPException, status
import redis

logger = logging.getLogger("SSEBackend.Database")

def get_redis_client():
    host = os.getenv("REDIS_HOST", "redis").strip().strip("'\"")
    port = int(os.getenv("REDIS_PORT", 6379))
    return redis.Redis(
        host=host,
        port=port,
        decode_responses=True
    )
