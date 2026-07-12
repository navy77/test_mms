import os
import sys
import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
import dotenv
from database import get_redis_client
from contextlib import asynccontextmanager
from routers.stream import router as stream_router, cache_manager
from fastapi import HTTPException

# Load environment variables
dotenv.load_dotenv(dotenv.find_dotenv())

# Add script directory to python path to ensure imports work correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)


from logging.handlers import RotatingFileHandler

# Configure logging
log_dir = os.path.join(script_dir, "log")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "stream_api.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=3),
        logging.StreamHandler(sys.stdout)
    ]
)
# Suppress watchfiles info logging to prevent log loops and spam
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logger = logging.getLogger("SSEApi")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background polling cache manager
    await cache_manager.start()
    yield
    # Stop background polling cache manager
    await cache_manager.stop()

app = FastAPI(
    title="MMS SSE Real-Time API",
    description="Backend API for Server-Sent Events real-time data streaming from Redis",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include SSE Router
app.include_router(stream_router)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    client = get_redis_client()
    try:
        await client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Redis connection failed: {e}"
        )

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0").strip().strip("'\"")
    port = int(os.getenv("SSE_PORT", os.getenv("PORT", 8002)))
    logger.info(f"Starting MMS SSE API Server at http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
