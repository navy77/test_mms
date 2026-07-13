import logging
import os
import json
import asyncio
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
import redis

from database import get_ch_client

logger = logging.getLogger("DashboardBackend.Stream")

router = APIRouter(prefix="/api/v1/device", tags=["DeviceRealtime"])

_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    host = os.getenv("REDIS_HOST", "redis").strip().strip("'\"")
    port = int(os.getenv("REDIS_PORT", 6379))
    try:
        r = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=2)
        r.ping()
        _redis_client = r
        return r
    except Exception as e:
        if host not in ("127.0.0.1", "localhost"):
            logger.info(
                f"Failed to connect to Redis at '{host}'. Trying fallback to '127.0.0.1'..."
            )
            try:
                r = redis.Redis(
                    host="127.0.0.1", port=port, decode_responses=True, socket_timeout=2
                )
                r.ping()
                _redis_client = r
                return r
            except Exception as inner_e:
                logger.error(f"Fallback to 127.0.0.1 also failed for Redis: {inner_e}")
                raise inner_e
        else:
            raise e


def get_division(postgres_client) -> str:
    try:
        query = "SELECT value FROM project_register_tb WHERE items = 'division'"
        result = postgres_client.query(query)
        if result.result_rows:
            return result.result_rows[0][0]
    except Exception as e:
        logger.warning(f"Error querying division from project_register_tb: {e}")
    return "mic"


@router.get("/realtime/status")
async def get_realtime_status_stream(
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
    db_client=Depends(get_ch_client),
):
    """
    SSE endpoint to fetch real-time device statuses from Redis 'rt_mqtt' hash.
    Streams only the requested devices to save bandwidth.
    """
    division = get_division(db_client)

    async def event_generator():
        logger.info(
            f"SSE status stream started for process={process}, devices={devices}"
        )
        device_list = [d.strip() for d in devices.split(",") if d.strip()]

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            poll_interval = 5.0

        try:
            while True:
                try:
                    r_client = get_redis_client()
                    fields = [
                        f"mqtt/{division}/{process}/{dev_id}" for dev_id in device_list
                    ]
                    values = r_client.hmget("rt_mqtt", fields)

                    response_data = []
                    for dev_id, val in zip(device_list, values):
                        if val:
                            try:
                                msg = json.loads(val)
                                payload = msg.get("payload")
                                if isinstance(payload, str):
                                    try:
                                        payload = json.loads(payload)
                                    except Exception:
                                        pass
                                response_data.append(
                                    {
                                        "device": dev_id,
                                        "status": "online",
                                        "payload": payload,
                                        "timestamp": msg.get("timestamp", ""),
                                    }
                                )
                            except Exception:
                                response_data.append(
                                    {
                                        "device": dev_id,
                                        "status": "online",
                                        "payload": {},
                                        "timestamp": "",
                                    }
                                )
                        else:
                            response_data.append(
                                {
                                    "device": dev_id,
                                    "status": "offline",
                                    "payload": {
                                        "broker": "—",
                                        "modbus": "—",
                                        "mac_id": "—",
                                    },
                                    "timestamp": "",
                                }
                            )

                    yield f"data: {json.dumps(response_data)}\n\n"
                except Exception as e:
                    logger.error(f"Error in SSE iteration: {e}")
                    fallback = [
                        {
                            "device": dev_id,
                            "status": "offline",
                            "payload": {"broker": "—", "modbus": "—", "mac_id": "—"},
                            "timestamp": "",
                        }
                        for dev_id in device_list
                    ]
                    yield f"data: {json.dumps(fallback)}\n\n"

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info(f"SSE client disconnected for process={process}")
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/realtime/machine-status")
async def get_realtime_machine_status_stream(
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
    db_client=Depends(get_ch_client),
):
    """
    SSE endpoint to fetch real-time machine statuses from Redis 'rt_status' hash.
    Streams only the requested devices to save bandwidth.
    """
    division = get_division(db_client)

    async def event_generator():
        logger.info(
            f"SSE machine-status stream started for process={process}, devices={devices}"
        )
        device_list = [d.strip() for d in devices.split(",") if d.strip()]

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            poll_interval = 5.0

        try:
            while True:
                try:
                    r_client = get_redis_client()
                    fields = [
                        f"status/{division}/{process}/{dev_id}"
                        for dev_id in device_list
                    ]
                    values = r_client.hmget("rt_status", fields)

                    response_data = []
                    for dev_id, val in zip(device_list, values):
                        if val:
                            try:
                                msg = json.loads(val)
                                payload_str = msg.get("payload")
                                status_val = "offline"
                                if payload_str:
                                    try:
                                        payload_data = json.loads(payload_str)
                                        if isinstance(payload_data, dict):
                                            status_val = str(
                                                payload_data.get("status", payload_str)
                                            )
                                        else:
                                            status_val = str(payload_data)
                                    except Exception:
                                        status_val = str(payload_str)

                                response_data.append(
                                    {
                                        "device": dev_id,
                                        "status": status_val,
                                        "timestamp": msg.get("timestamp", ""),
                                    }
                                )
                            except Exception:
                                response_data.append(
                                    {
                                        "device": dev_id,
                                        "status": "offline",
                                        "timestamp": "",
                                    }
                                )
                        else:
                            response_data.append(
                                {
                                    "device": dev_id,
                                    "status": "offline",
                                    "timestamp": "",
                                }
                            )

                    yield f"data: {json.dumps(response_data)}\n\n"
                except Exception as e:
                    logger.error(f"Error in SSE iteration for machine status: {e}")
                    fallback = [
                        {"device": dev_id, "status": "offline", "timestamp": ""}
                        for dev_id in device_list
                    ]
                    yield f"data: {json.dumps(fallback)}\n\n"

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info(f"SSE machine-status client disconnected for process={process}")
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/realtime/alarm-status")
async def get_realtime_alarm_status_stream(
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
    db_client=Depends(get_ch_client),
):
    """
    SSE endpoint to fetch real-time alarm statuses from Redis 'rt_alarm' hash.
    Streams only the requested devices to save bandwidth.
    """
    division = get_division(db_client)

    async def event_generator():
        logger.info(
            f"SSE alarm-status stream started for process={process}, devices={devices}"
        )
        device_list = [d.strip() for d in devices.split(",") if d.strip()]

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            poll_interval = 5.0

        try:
            while True:
                try:
                    r_client = get_redis_client()
                    fields = [
                        f"alarm/{division}/{process}/{dev_id}" for dev_id in device_list
                    ]
                    values = r_client.hmget("rt_alarm", fields)

                    response_data = []
                    for dev_id, val in zip(device_list, values):
                        if val:
                            try:
                                msg = json.loads(val)
                                payload_str = msg.get("payload")
                                status_val = "normal"
                                if payload_str:
                                    try:
                                        payload_data = json.loads(payload_str)
                                        if isinstance(payload_data, dict):
                                            status_val = str(
                                                payload_data.get("status", payload_str)
                                            )
                                        else:
                                            status_val = str(payload_data)
                                    except Exception:
                                        status_val = str(payload_str)

                                response_data.append(
                                    {
                                        "device": dev_id,
                                        "status": status_val,
                                        "timestamp": msg.get("timestamp", ""),
                                    }
                                )
                            except Exception:
                                response_data.append(
                                    {
                                        "device": dev_id,
                                        "status": "normal",
                                        "timestamp": "",
                                    }
                                )
                        else:
                            response_data.append(
                                {
                                    "device": dev_id,
                                    "status": "normal",
                                    "timestamp": "",
                                }
                            )

                    yield f"data: {json.dumps(response_data)}\n\n"
                except Exception as e:
                    logger.error(f"Error in SSE iteration for alarm status: {e}")
                    fallback = [
                        {"device": dev_id, "status": "normal", "timestamp": ""}
                        for dev_id in device_list
                    ]
                    yield f"data: {json.dumps(fallback)}\n\n"

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info(f"SSE alarm-status client disconnected for process={process}")
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")
