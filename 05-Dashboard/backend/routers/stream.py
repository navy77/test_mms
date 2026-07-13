import logging
import os
import json
import asyncio
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
import redis

from datetime import datetime, timedelta, timezone
from typing import List, Any, Dict, Optional
from database import (
    PostgresClient,
    format_result,
    get_clickhouse_client,
    get_db_connection,
    release_db_connection,
)


logger = logging.getLogger("DashboardBackend.Stream")


# Bangkok timezone (+07:00)
TZ_BANGKOK = timezone(timedelta(hours=7))


def get_now_bangkok() -> datetime:
    return datetime.now(TZ_BANGKOK)


def get_production_day_range(dt: datetime):
    """
    Given a datetime in Bangkok timezone, calculate the start and end of its production day.
    Production day starts at 07:00:00 of the day and ends at 06:59:59 of the next day (inclusive).
    If the time is between 00:00:00 and 06:59:59, the production day is actually the previous day.
    """
    if dt.hour < 7:
        prod_date = (dt - timedelta(days=1)).date()
    else:
        prod_date = dt.date()

    start_dt = (
        datetime.combine(prod_date, datetime.min.time(), tzinfo=dt.tzinfo)
        + timedelta(hours=7)
    )
    end_dt = start_dt + timedelta(days=1) - timedelta(microseconds=1)
    return start_dt, end_dt


def get_initial_statuses_batch(
    client, process: str, start_time: datetime, devices: Optional[List[str]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Query the latest status of all devices (or specified devices) before start_time in a single query.
    Returns a dictionary mapping device_name -> {"status": status, "created_at": datetime}.
    """
    try:
        device_filter = ""
        parameters = {"process": process, "start_time": start_time}
        if devices:
            device_filter = "AND device IN %(devices)s"
            parameters["devices"] = devices

        query = f"""
            SELECT device, status, created_at FROM status_tb
            WHERE process = %(process)s
              {device_filter}
              AND created_at < %(start_time)s
            ORDER BY created_at DESC
            LIMIT 1 BY device
        """
        result = client.query(query, parameters=parameters)
        return {
            row[0]: {"status": row[1], "created_at": row[2]} for row in result.result_rows
        }
    except Exception as e:
        logger.warning(
            f"Error batch fetching initial statuses for process '{process}': {e}"
        )
        return {}


def calculate_status_timeline(
    records: List[Dict[str, Any]],
    start_time: datetime,
    end_time: datetime,
    initial_status: Optional[Dict[str, Any]],
    device: str,
    ) -> List[Dict[str, Any]]:
    """
    Given status records for a device, calculates the sequential timeline of status states.
    Consecutive status updates with the same status value are merged into a single segment.
    """
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=TZ_BANGKOK)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=TZ_BANGKOK)

    # Establish initial state at start_time
    if initial_status:
        init_val = initial_status.get("status", "unknown")
    else:
        init_val = "no data"

    raw_changes = [{"created_at": start_time, "status": init_val}]

    # Parse and filter records to make sure they are within bounds
    parsed_records = []
    for r in records:
        ca = r.get("created_at")
        if isinstance(ca, str):
            ca = datetime.fromisoformat(ca)
        if ca.tzinfo is None:
            ca = ca.replace(tzinfo=TZ_BANGKOK)

        if start_time <= ca <= end_time:
            parsed_records.append(
                {"created_at": ca, "status": str(r.get("status", "unknown"))}
            )

    parsed_records.sort(key=lambda x: x["created_at"])
    raw_changes.extend(parsed_records)

    # Merge contiguous segments with same status
    merged_changes = []
    for change in raw_changes:
        if not merged_changes:
            merged_changes.append(change)
        else:
            if merged_changes[-1]["status"] == change["status"]:
                continue
            else:
                merged_changes.append(change)

    # Now generate the timeline segments
    timeline = []
    for i in range(len(merged_changes)):
        curr = merged_changes[i]
        curr_ts = curr["created_at"]
        curr_status = curr["status"]

        if i < len(merged_changes) - 1:
            next_ts = merged_changes[i + 1]["created_at"]
        else:
            next_ts = end_time

        duration = max(0.0, (next_ts - curr_ts).total_seconds())
        duration = round(duration, 1)

        # Output segment if duration > 0 or if it's the only segment
        if duration > 0 or len(merged_changes) == 1:
            timeline.append(
                {
                    "status": curr_status,
                    "start_time": curr_ts.isoformat(),
                    "end_time": next_ts.isoformat(),
                    "duration": duration,
                }
            )

    return timeline


router = APIRouter(prefix="/api/v1/device", tags=["DeviceRealtime"])


_redis_client = None


def parse_devices(devices: str) -> list[str]:
    """Parse, deduplicate, and cap device IDs accepted by an SSE connection."""
    device_list = list(dict.fromkeys(item.strip() for item in devices.split(",") if item.strip()))
    max_devices = int(os.getenv("SSE_MAX_DEVICES", "100"))
    if not device_list:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="devices is required")
    if len(device_list) > max_devices:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Maximum {max_devices} devices per stream")
    return device_list


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


def get_stream_division() -> str:
    """Read division without retaining a PostgreSQL connection for the SSE lifetime."""
    connection = get_db_connection()
    try:
        return get_division(PostgresClient(connection))
    finally:
        release_db_connection(connection)


@router.get("/realtime/status")
async def get_realtime_status_stream(
    request: Request,
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
):
    """
    SSE endpoint to fetch real-time device statuses from Redis 'rt_mqtt' hash.
    Streams only the requested devices to save bandwidth.
    """
    division = get_stream_division()

    async def event_generator():
        logger.info(
            f"SSE status stream started for process={process}, devices={devices}"
        )
        device_list = parse_devices(devices)

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            poll_interval = 5.0

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    r_client = get_redis_client()
                    fields = [
                        f"mqtt/{division}/{process}/{dev_id}" for dev_id in device_list
                    ]
                    values = await asyncio.to_thread(r_client.hmget, "rt_mqtt", fields)

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
    request: Request,
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
):
    """
    SSE endpoint to fetch real-time machine statuses from Redis 'rt_status' hash.
    Streams only the requested devices to save bandwidth.
    """
    division = get_stream_division()

    async def event_generator():
        logger.info(
            f"SSE machine-status stream started for process={process}, devices={devices}"
        )
        device_list = parse_devices(devices)

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            poll_interval = 5.0

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    r_client = get_redis_client()
                    fields = [
                        f"status/{division}/{process}/{dev_id}"
                        for dev_id in device_list
                    ]
                    values = await asyncio.to_thread(r_client.hmget, "rt_status", fields)

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
    request: Request,
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
):
    """
    SSE endpoint to fetch real-time alarm statuses from Redis 'rt_alarm' hash.
    Streams only the requested devices to save bandwidth.
    """
    division = get_stream_division()

    async def event_generator():
        logger.info(
            f"SSE alarm-status stream started for process={process}, devices={devices}"
        )
        device_list = parse_devices(devices)

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            poll_interval = 5.0

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    r_client = get_redis_client()
                    fields = [
                        f"alarm/{division}/{process}/{dev_id}" for dev_id in device_list
                    ]
                    values = await asyncio.to_thread(r_client.hmget, "rt_alarm", fields)

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


@router.get("/realtime/state-timeline")
async def get_realtime_state_timeline_stream(
    request: Request,
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
):
    """
    SSE endpoint to fetch real-time state timelines for multiple devices.
    Streams updated timelines starting from 07:00 of the current production day until now.
    """
    async def event_generator():
        logger.info(
            f"SSE state timeline stream started for process={process}, devices={devices}"
        )
        device_list = parse_devices(devices)

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 10.0))
        except ValueError:
            poll_interval = 10.0

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    if not device_list:
                        yield f"data: {json.dumps({})}\n\n"
                        await asyncio.sleep(poll_interval)
                        continue

                    client = await asyncio.to_thread(get_clickhouse_client)
                    now = get_now_bangkok()
                    start_time, _ = get_production_day_range(now)

                    # Fetch initial statuses for all requested devices at once
                    initial_statuses = await asyncio.to_thread(
                        get_initial_statuses_batch,
                        client,
                        process,
                        start_time,
                        device_list,
                    )

                    # Query all status records for all requested devices since start_time
                    query = """
                        SELECT process, device, status, created_at
                        FROM status_tb
                        WHERE process = %(process)s
                          AND device IN %(devices)s
                          AND created_at >= %(start_time)s
                          AND created_at <= %(end_time)s
                        ORDER BY created_at ASC
                    """
                    result = await asyncio.to_thread(
                        client.query,
                        query,
                        parameters={
                            "process": process,
                            "devices": device_list,
                            "start_time": start_time,
                            "end_time": now,
                        },
                    )
                    records = format_result(result)

                    # Group records by device
                    grouped_records = {dev: [] for dev in device_list}
                    for r in records:
                        dev = r.get("device")
                        if dev in grouped_records:
                            grouped_records[dev].append(r)

                    # Calculate timeline for each device
                    response_payload = {}
                    for dev in device_list:
                        dev_records = grouped_records[dev]
                        init_status = initial_statuses.get(dev)
                        timeline_data = calculate_status_timeline(
                            dev_records, start_time, now, init_status, dev
                        )
                        response_payload[dev] = timeline_data

                    yield f"data: {json.dumps(response_payload)}\n\n"
                except Exception as e:
                    logger.error(f"Error in SSE state timeline iteration: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info(
                f"SSE state timeline client disconnected for process={process}, devices={devices}"
            )
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/realtime/data")
async def get_realtime_data_stream(
    request: Request,
    process: str = Query(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated list of device IDs"),
):
    """
    SSE endpoint to fetch real-time production data from Redis 'rt_data' hash.
    Streams only the requested devices to save bandwidth.
    """
    division = get_stream_division()

    async def event_generator():
        logger.info(f"SSE data stream started for process={process}, devices={devices}")
        device_list = parse_devices(devices)

        try:
            poll_interval = float(os.getenv("SSE_POLL_INTERVAL", 5.0))
        except ValueError:
            poll_interval = 5.0

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    r_client = get_redis_client()
                    fields = [
                        f"data/{division}/{process}/{dev_id}" for dev_id in device_list
                    ]
                    values = await asyncio.to_thread(r_client.hmget, "rt_data", fields)

                    response_data = []
                    for dev_id, val in zip(device_list, values):
                        if val:
                            try:
                                msg = json.loads(val)
                                payload = msg.get("payload")
                                if isinstance(payload, str):
                                    try:
                                        payload = json.loads(payload)
                                    except json.JSONDecodeError:
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
                                    "status": "no_data",
                                    "payload": {},
                                    "timestamp": "",
                                }
                            )

                    yield f"data: {json.dumps(response_data)}\n\n"
                except Exception as e:
                    logger.error(f"Error in SSE iteration for data stream: {e}")
                    fallback = [
                        {
                            "device": dev_id,
                            "status": "no_data",
                            "payload": {},
                            "timestamp": "",
                        }
                        for dev_id in device_list
                    ]
                    yield f"data: {json.dumps(fallback)}\n\n"

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info(f"SSE data client disconnected for process={process}")
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")
