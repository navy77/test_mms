import json
import logging
import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from database import get_redis_client
import redis

logger = logging.getLogger("SSEBackend.SSERouter")

router = APIRouter(
    prefix="/api",
    tags=["stream"]
)

@router.get("/realtime/{category}/{process}")
async def get_realtime_stream(
    category: str, 
    process: str, 
    redis_client = Depends(get_redis_client)
):
    valid_categories = ["data", "status", "alarm", "mqtt"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )

    

    async def event_generator():
        logger.info(f"Real-time stream started for category={category}, process={process}")
        redis_key = f"rt_{category}"
        try:
            while True:
                try:
                    # Fetch all keys/values from the Redis hash
                    redis_data = await redis_client.hgetall(redis_key)
                    
                    matched_messages = []
                    for topic, val_str in redis_data.items():
                        try:
                            msg = json.loads(val_str)
                            # Check if process matches the path parameter
                            if msg.get("process") == process:
                                matched_messages.append(msg)
                        except Exception:
                            # Fallback parsing directly from the MQTT topic structure: category/div/process/device
                            parts = topic.split('/')
                            if len(parts) >= 4 and parts[2] == process:
                                matched_messages.append({
                                    "topic": topic,
                                    "div": parts[1],
                                    "process": parts[2],
                                    "device": parts[3],
                                    "payload": val_str,
                                    "timestamp": ""
                                })

                    # Send out the matched messages as SSE event
                    yield f"data: {json.dumps(matched_messages)}\n\n"
                
                except redis.exceptions.RedisError as re:
                    logger.error(f"Failed to read from Redis hash '{redis_key}': {re}")
                    yield f"data: {json.dumps({'error': 'Redis database connection lost'})}\n\n"

                # Wait 10 seconds before the next update
                await asyncio.sleep(10)
                
        except asyncio.CancelledError:
            logger.info(f"Client disconnected from stream for category={category}, process={process}")
            raise
        except Exception as e:
            logger.error(f"Error in real-time stream generator: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
