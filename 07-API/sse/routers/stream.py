import os
import json
import logging
import asyncio
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from database import get_redis_client

logger = logging.getLogger("SSEBackend.SSERouter")

class RealtimeCacheManager:
    def __init__(self):
        self.cache = {
            "data": {},
            "status": {},
            "alarm": {},
            "mqtt": {}
        }
        self.poll_interval = 2.0
        self.task = None
        self.is_running = False

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        try:
            self.poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            self.poll_interval = 5.0
        
        self.task = asyncio.create_task(self._poll_loop())
        logger.info(f"RealtimeCacheManager background polling task started (interval={self.poll_interval}s).")

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("RealtimeCacheManager background polling task stopped.")

    async def _poll_loop(self):
        redis_client = get_redis_client()
        categories = ["data", "status", "alarm", "mqtt"]
        while self.is_running:
            for category in categories:
                redis_key = f"rt_{category}"
                try:
                    redis_data = await redis_client.hgetall(redis_key)
                    parsed_data = {}
                    for topic, val_str in redis_data.items():
                        try:
                            msg = json.loads(val_str)
                            parsed_data[topic] = msg
                        except Exception:
                            parts = topic.split('/')
                            if len(parts) >= 4:
                                parsed_data[topic] = {
                                    "topic": topic,
                                    "div": parts[1],
                                    "process": parts[2],
                                    "device": parts[3],
                                    "payload": val_str,
                                    "timestamp": ""
                                }
                    self.cache[category] = parsed_data
                except Exception as e:
                    logger.error(f"Error updating cache for {category}: {e}")
            
            await asyncio.sleep(self.poll_interval)

    def get_data(self, category: str, process: str) -> list:
        category_cache = self.cache.get(category, {})
        matched = []
        for topic, msg in category_cache.items():
            if msg.get("process") == process:
                matched.append(msg)
        return matched

cache_manager = RealtimeCacheManager()

router = APIRouter(
    prefix="/api/v1",
    tags=["stream"]
)

@router.get("/realtime/{category}/{process}")
async def get_realtime_stream(category: str, process: str):
    valid_categories = ["data", "status", "alarm", "mqtt"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
        )

    async def event_generator():
        logger.info(f"Real-time stream started for category={category}, process={process}")
        try:
            import os
            try:
                poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
            except ValueError:
                poll_interval = 5.0
            while True:
                matched_messages = cache_manager.get_data(category, process)
                yield f"data: {json.dumps(matched_messages)}\n\n"
                await asyncio.sleep(poll_interval)
                
        except asyncio.CancelledError:
            logger.info(f"Client disconnected from stream for category={category}, process={process}")
            raise
        except Exception as e:
            logger.error(f"Error in real-time stream generator: {e}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

