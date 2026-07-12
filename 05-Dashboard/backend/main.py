import os
import sys
import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
import dotenv

# Load environment variables
dotenv.load_dotenv(dotenv.find_dotenv())

# Add script directory to python path to ensure imports work correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from database import get_ch_client
from routers.register import router as register_router
from routers.auth import router as auth_router

from logging.handlers import RotatingFileHandler

# Configure logging
log_dir = os.path.join(script_dir, "log")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "dashboard_backend.log")

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
logger = logging.getLogger("DashboardBackend")

app = FastAPI(
    title="MMS Dashboard API",
    description="Backend API for User, Device, and Column Registration",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(register_router)

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    client = get_ch_client()
    return {"status": "healthy", "clickhouse": "connected"}

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0").strip().strip("'\"")
    port = int(os.getenv("DASHBOARD_PORT", os.getenv("PORT", 8001)))
    logger.info(f"Starting MMS Dashboard Backend Server at http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
