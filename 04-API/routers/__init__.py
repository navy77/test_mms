from .data import router as data_router
from .status import router as status_router
from .alarm import router as alarm_router
from .device import router as device_router

__all__ = ["data_router", "status_router", "alarm_router", "device_router"]

