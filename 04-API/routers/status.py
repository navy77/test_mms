import logging
import calendar
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import List, Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Path, Query, status
from database import get_ch_client, format_result
from models import StatusResponse, DailyStatusResponse, MonthlyStatusResponse, StatusSegment, TimelineResponse, TimelineSegment

logger = logging.getLogger("RESTBackend.Routers.Status")
router = APIRouter(prefix="/api/v1/status", tags=["Status"])

# ── In-memory TTL Cache (60 sec) for state timeline ─────────────────────────
try:
    from cachetools import TTLCache
    _state_cache: TTLCache = TTLCache(maxsize=500, ttl=60)
except ImportError:
    # Fallback: plain dict (no TTL) — install cachetools for full benefit
    _state_cache = {}  # type: ignore
_cache_lock = Lock()

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
    
    start_dt = datetime.combine(prod_date, datetime.min.time(), tzinfo=dt.tzinfo) + timedelta(hours=7)
    end_dt = start_dt + timedelta(days=1) - timedelta(microseconds=1)
    return start_dt, end_dt

def get_registered_devices(client, process: str) -> List[str]:
    """
    Retrieve registered device names for the given process from device_register_tb.
    """
    try:
        query = "SELECT device FROM configdb.device_register_tb WHERE process = %(process)s"
        result = client.query(query, parameters={"process": process})
        return [row[0] for row in result.result_rows]
    except Exception as e:
        logger.warning(f"Error querying configdb.device_register_tb for process '{process}': {e}")
        return []

def get_initial_statuses_batch(client, process: str, start_time: datetime, devices: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
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
        return {row[0]: {"status": row[1], "created_at": row[2]} for row in result.result_rows}
    except Exception as e:
        logger.warning(f"Error batch fetching initial statuses for process '{process}': {e}")
        return {}

def calculate_status_ratio(
    records: List[Dict[str, Any]], 
    start_time: datetime, 
    end_time: datetime,
    initial_status: Optional[Dict[str, Any]],
    device: str
) -> List[StatusSegment]:
    """
    Implements the exact status ratio calculation logic from the reference code in pure Python.
    """
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=TZ_BANGKOK)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=TZ_BANGKOK)

    # 1. Prepare raw record list
    df_list = []
    
    if not records:  # df2 is empty
        if not initial_status:  # df1 is empty
            df_list = [{"created_at": start_time, "status": "no data"}]
        else:  # df1 has data
            df_list = [{"created_at": start_time, "status": initial_status["status"]}]
    else:  # df2 is not empty
        # Parse all records in range
        parsed_records = []
        for r in records:
            ca = r.get("created_at")
            if isinstance(ca, str):
                ca = datetime.fromisoformat(ca)
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=TZ_BANGKOK)
            parsed_records.append({
                "created_at": ca,
                "status": r.get("status", "unknown")
            })
        
        parsed_records.sort(key=lambda x: x["created_at"])
            
        if not initial_status:  # df1 is empty
            first_status = "no data"
            df_list = [{"created_at": start_time, "status": first_status}] + parsed_records
        else:  # df1 has data
            df_list = [{"created_at": start_time, "status": initial_status["status"]}] + parsed_records

    # 2. Sort all by timestamp
    df_list.sort(key=lambda x: x["created_at"])
    
    # 3. Calculate next_ts and duration
    total_duration = 0.0
    status_durations = {}
    
    for i in range(len(df_list)):
        curr_rec = df_list[i]
        curr_ts = curr_rec["created_at"]
        curr_status = str(curr_rec["status"])
        
        if i < len(df_list) - 1:
            next_ts = df_list[i+1]["created_at"]
        else:
            next_ts = end_time
            
        duration = max(0.0, (next_ts - curr_ts).total_seconds())
        duration = round(duration, 1)
        
        status_durations[curr_status] = status_durations.get(curr_status, 0.0) + duration
        total_duration += duration

    # 4. Find ratio %
    results = []
    if total_duration > 0:
        for status_name, duration in status_durations.items():
            ratio = round((duration / total_duration) * 100, 1)
            results.append(
                StatusSegment(
                    status=status_name,
                    duration=duration,
                    ratio=ratio
                )
            )
    else:
        results = [StatusSegment(status="no data", duration=0.0, ratio=0.0)]
        
    return results


def calculate_utilization_percentage(segments: List[StatusSegment]) -> float:
    """
    Calculate utilization percentage, excluding 'stop' and 'no data' statuses.
    Formula: run / (alarm + wait + other + run)
    """
    run_duration = sum(seg.duration for seg in segments if seg.status == "run")
    active_duration = sum(seg.duration for seg in segments if seg.status not in ["stop", "no data"])
    return round((run_duration / active_duration) * 100, 1) if active_duration > 0 else 0.0


def calculate_status_timeline(
    records: List[Dict[str, Any]], 
    start_time: datetime, 
    end_time: datetime,
    initial_status: Optional[Dict[str, Any]],
    device: str
) -> List[TimelineSegment]:
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
            parsed_records.append({
                "created_at": ca,
                "status": str(r.get("status", "unknown"))
            })

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
            next_ts = merged_changes[i+1]["created_at"]
        else:
            next_ts = end_time

        duration = max(0.0, (next_ts - curr_ts).total_seconds())
        duration = round(duration, 1)

        # Output segment if duration > 0 or if it's the only segment
        if duration > 0 or len(merged_changes) == 1:
            timeline.append(
                TimelineSegment(
                    status=curr_status,
                    start_time=curr_ts.isoformat(),
                    end_time=next_ts.isoformat(),
                    duration=duration
                )
            )

    return timeline

def group_status_by_device(
    records: List[Dict[str, Any]],
    devices: List[str],
    start_time: datetime,
    end_time: datetime,
    initial_statuses: Dict[str, Dict[str, Any]]
) -> List[StatusResponse]:
    """
    Groups currently status records by device and calculates status ratio segments.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        dev = r.get("device", "unknown")
        if dev not in groups:
            groups[dev] = []
        groups[dev].append(r)
        
    all_devices = list(set(devices + list(groups.keys())))
    all_devices.sort()
    
    results = []
    for dev in all_devices:
        dev_records = groups.get(dev, [])
        init_status = initial_statuses.get(dev)
        segments = calculate_status_ratio(dev_records, start_time, end_time, init_status, dev)
        utilize = calculate_utilization_percentage(segments)
        results.append(
            StatusResponse(
                device=dev,
                data=segments,
                utilize=utilize
            )
        )
    return results

def group_status_by_prod_date(
    records: List[Dict[str, Any]],
    devices: List[str],
    start_date,
    end_date,
    initial_statuses: Dict[str, Dict[str, Any]]
) -> List[DailyStatusResponse]:
    """
    Groups status records by day (production date) and device, computing status ratio segments.
    Carries forward device status from day to day purely in Python.
    """
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in records:
        ca = r.get("created_at")
        if isinstance(ca, str):
            dt = datetime.fromisoformat(ca)
        elif isinstance(ca, datetime):
            dt = ca
        else:
            dt = get_now_bangkok()
            
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_BANGKOK)
            
        if dt.hour < 7:
            prod_date = (dt - timedelta(days=1)).date()
        else:
            prod_date = dt.date()
            
        prod_date_str = prod_date.isoformat()
        dev = r.get("device", "unknown")
        
        key = (prod_date_str, dev)
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
        
    date_list = []
    curr = start_date
    while curr <= end_date:
        date_list.append(curr)
        curr += timedelta(days=1)
        
    all_devices = list(set(devices + [r.get("device") for r in records if r.get("device")]))
    all_devices.sort()
    
    # Track the active status of each device.
    # At start_date, the active status is determined by initial_statuses
    active_statuses = {}
    for dev in all_devices:
        init = initial_statuses.get(dev)
        if init:
            active_statuses[dev] = init["status"]
        else:
            active_statuses[dev] = "no data"
            
    # Get current production date in Bangkok timezone
    now = get_now_bangkok()
    if now.hour < 7:
        current_prod_date = (now - timedelta(days=1)).date()
    else:
        current_prod_date = now.date()
            
    results = []
    for d in date_list:
        d_str = d.isoformat()
        day_start = datetime.combine(d, datetime.min.time(), tzinfo=TZ_BANGKOK) + timedelta(hours=7)
        day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)
        
        for dev in all_devices:
            day_records = groups.get((d_str, dev), [])
            # Sort day_records chronologically
            day_records.sort(key=lambda x: x.get("created_at") if isinstance(x.get("created_at"), datetime) else datetime.fromisoformat(x.get("created_at")))
            
            init_status = {"status": active_statuses[dev]} if active_statuses[dev] else None
            
            if d < current_prod_date:
                segments = calculate_status_ratio(day_records, day_start, day_end, init_status, dev)
            elif d == current_prod_date:
                segments = calculate_status_ratio(day_records, day_start, now, init_status, dev)
            else:
                segments = []
                
            results.append(
                DailyStatusResponse(
                    date=d_str,
                    device=dev,
                    data=segments,
                    utilize=calculate_utilization_percentage(segments)
                )
            )
            
            # Update active status for the next day to the status of the last record of today
            if day_records:
                active_statuses[dev] = day_records[-1].get("status", "unknown")
                
    return results

def group_status_by_month(
    records: List[Dict[str, Any]],
    month_str: str,
    devices: List[str],
    start_time: datetime,
    end_time: datetime,
    initial_statuses: Dict[str, Dict[str, Any]]
) -> List[MonthlyStatusResponse]:
    """
    Groups status records by device for the entire month, calculating status ratio segments.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        dev = r.get("device", "unknown")
        if dev not in groups:
            groups[dev] = []
        groups[dev].append(r)
        
    all_devices = list(set(devices + list(groups.keys())))
    all_devices.sort()
    
    results = []
    for dev in all_devices:
        dev_records = groups.get(dev, [])
        init_status = initial_statuses.get(dev)
        segments = calculate_status_ratio(dev_records, start_time, end_time, init_status, dev)
        utilize = calculate_utilization_percentage(segments)
        results.append(
            MonthlyStatusResponse(
                month=month_str,
                device=dev,
                data=segments,
                utilize=utilize
            )
        )
    return results

# 1. currently Endpoints
@router.get("/currently/{process}", response_model=List[StatusResponse])
def get_currently_process(
    process: str = Path(..., description="The process identifier")
):
    """
    Get currently status segments for all devices in a process from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching currently status for process '{process}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        devices = get_registered_devices(client, process)
        initial_statuses = get_initial_statuses_batch(client, process, start_time, devices)
        
        query = """
            SELECT process, device, status, created_at
            FROM status_tb
            WHERE process = %(process)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "start_time": start_time,
                "end_time": now
            }
        )
        records = format_result(result)
        
        has_data = len(records) > 0 or len(initial_statuses) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_status_by_device(records, devices, start_time, now, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching currently process status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/currently/{process}/{device}", response_model=StatusResponse)
def get_currently_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get currently status segments for a specific device from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching currently status for device '{process}/{device}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        initial_statuses = get_initial_statuses_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM status_tb
            WHERE process = %(process)s
              AND device = %(device)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "device": device,
                "start_time": start_time,
                "end_time": now
            }
        )
        records = format_result(result)
        
        has_data = len(records) > 0 or len(initial_statuses) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        res = group_status_by_device(records, [device], start_time, now, initial_statuses)
        if res:
            return res[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching currently device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 2. Daily Endpoints
@router.get("/daily/{process}", response_model=List[DailyStatusResponse])
def get_daily_process(
    process: str = Path(..., description="The process identifier")
):
    """
    Get daily status segments for all devices in a process for the current production month.
    """
    now = get_now_bangkok()
    if now.hour < 7:
        prod_date = (now - timedelta(days=1)).date()
    else:
        prod_date = now.date()
        
    start_date = prod_date.replace(day=1)
    last_day = calendar.monthrange(prod_date.year, prod_date.month)[1]
    end_date = prod_date.replace(day=last_day)
    
    start_time = datetime.combine(start_date, datetime.min.time(), tzinfo=TZ_BANGKOK) + timedelta(hours=7)
    end_time = datetime.combine(end_date, datetime.max.time(), tzinfo=TZ_BANGKOK)
    
    logger.info(f"Fetching daily status for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        devices = get_registered_devices(client, process)
        initial_statuses = get_initial_statuses_batch(client, process, start_time, devices)
        
        query = """
            SELECT process, device, status, created_at
            FROM status_tb
            WHERE process = %(process)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "start_time": start_time,
                "end_time": end_time
            }
        )
        records = format_result(result)
        
        has_data = len(records) > 0 or len(initial_statuses) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_status_by_prod_date(records, devices, start_date, end_date, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily process status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/daily/{process}/{device}", response_model=List[DailyStatusResponse])
def get_daily_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get daily status segments for a specific device for the current production month.
    """
    now = get_now_bangkok()
    if now.hour < 7:
        prod_date = (now - timedelta(days=1)).date()
    else:
        prod_date = now.date()
        
    start_date = prod_date.replace(day=1)
    last_day = calendar.monthrange(prod_date.year, prod_date.month)[1]
    end_date = prod_date.replace(day=last_day)
    
    start_time = datetime.combine(start_date, datetime.min.time(), tzinfo=TZ_BANGKOK) + timedelta(hours=7)
    end_time = datetime.combine(end_date, datetime.max.time(), tzinfo=TZ_BANGKOK)
    
    logger.info(f"Fetching daily status for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        initial_statuses = get_initial_statuses_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM status_tb
            WHERE process = %(process)s
              AND device = %(device)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "device": device,
                "start_time": start_time,
                "end_time": end_time
            }
        )
        records = format_result(result)
        
        has_data = len(records) > 0 or len(initial_statuses) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_status_by_prod_date(records, [device], start_date, end_date, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 3. Monthly Endpoints
@router.get("/monthly/{year}/{month}/{process}", response_model=List[MonthlyStatusResponse])
def get_monthly_process(
    year: int = Path(..., description="The query year (e.g. 2026)", ge=2000),
    month: int = Path(..., description="The query month (1-12)", ge=1, le=12),
    process: str = Path(..., description="The process identifier")
):
    """
    Get status segments for all devices in a process for a specific month.
    """
    start_time = datetime(year, month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    end_time = datetime(next_year, next_month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    now = get_now_bangkok()
    if end_time > now:
        end_time = max(start_time, now)
    
    logger.info(f"Fetching monthly status for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        devices = get_registered_devices(client, process)
        initial_statuses = get_initial_statuses_batch(client, process, start_time, devices)
        
        query = """
            SELECT process, device, status, created_at
            FROM status_tb
            WHERE process = %(process)s
              AND created_at >= %(start_time)s
              AND created_at < %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "start_time": start_time,
                "end_time": end_time
            }
        )
        records = format_result(result)
        
        has_data = len(records) > 0 or len(initial_statuses) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_status_by_month(records, f"{year}-{month:02d}", devices, start_time, end_time, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly process status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/monthly/{year}/{month}/{process}/{device}", response_model=List[MonthlyStatusResponse])
def get_monthly_device(
    year: int = Path(..., description="The query year (e.g. 2026)", ge=2000),
    month: int = Path(..., description="The query month (1-12)", ge=1, le=12),
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get status segments for a specific device in a process for a specific month.
    """
    start_time = datetime(year, month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    end_time = datetime(next_year, next_month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    now = get_now_bangkok()
    if end_time > now:
        end_time = max(start_time, now)
    
    logger.info(f"Fetching monthly status for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        initial_statuses = get_initial_statuses_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM status_tb
            WHERE process = %(process)s
              AND device = %(device)s
              AND created_at >= %(start_time)s
              AND created_at < %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "device": device,
                "start_time": start_time,
                "end_time": end_time
            }
        )
        records = format_result(result)
        
        has_data = len(records) > 0 or len(initial_statuses) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_status_by_month(records, f"{year}-{month:02d}", [device], start_time, end_time, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 4a. State status — BATCH (single ClickHouse query for multiple devices)
@router.get("/state/{process}")
def get_state_status_batch(
    process: str = Path(..., description="The process identifier"),
    devices: str = Query(..., description="Comma-separated device names, e.g. no_1,no_2,no_3"),
):
    """
    Batch endpoint: fetch state timelines for multiple devices in ONE ClickHouse query.
    Per-device results are cached for 60 seconds (shared with single-device endpoint).
    Response: { "no_1": [...segments], "no_2": [...segments], ... }
    """
    from collections import defaultdict

    device_list = [d.strip() for d in devices.split(",") if d.strip()]
    if not device_list:
        raise HTTPException(status_code=400, detail="devices query param is required")

    now = get_now_bangkok()
    start_time, _ = get_production_day_range(now)

    # ── 1. Check cache per device ────────────────────────────────────────────
    result: Dict[str, Any] = {}
    to_fetch: List[str] = []
    for dev in device_list:
        cache_key = (process, dev, start_time.date().isoformat())
        with _cache_lock:
            cached = _state_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT (batch): state {process}/{dev}")
            result[dev] = [seg.__dict__ if hasattr(seg, "__dict__") else seg for seg in cached]
        else:
            to_fetch.append(dev)

    if not to_fetch:
        return result

    # ── 2. Single ClickHouse query for all uncached devices ──────────────────
    logger.info(f"Batch fetching state timeline: {process}/{to_fetch} from {start_time} to {now}")
    client = get_ch_client()
    try:
        initial_statuses = get_initial_statuses_batch(client, process, start_time, to_fetch)

        query = """
            SELECT device, status, created_at
            FROM status_tb
            WHERE process = %(process)s
              AND device IN %(devices)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY device, created_at ASC
        """
        ch_result = client.query(
            query,
            parameters={
                "process": process,
                "devices": to_fetch,
                "start_time": start_time,
                "end_time": now,
            },
        )

        # Group raw rows by device
        records_by_device: Dict[str, List] = defaultdict(list)
        for row in ch_result.result_rows:
            records_by_device[row[0]].append(
                {"device": row[0], "status": row[1], "created_at": row[2]}
            )

        # ── 3. Calculate timeline per device and cache ───────────────────────
        for dev in to_fetch:
            init_status = initial_statuses.get(dev)
            dev_records = records_by_device.get(dev, [])
            timeline_data = calculate_status_timeline(
                dev_records, start_time, now, init_status, dev
            )
            cache_key = (process, dev, start_time.date().isoformat())
            with _cache_lock:
                _state_cache[cache_key] = timeline_data
            result[dev] = [
                {
                    "start_time": seg.start_time.isoformat() if hasattr(seg, "start_time") else seg["start_time"],
                    "end_time": seg.end_time.isoformat() if hasattr(seg, "end_time") else seg["end_time"],
                    "status": seg.status if hasattr(seg, "status") else seg["status"],
                    "duration": seg.duration if hasattr(seg, "duration") else seg["duration"],
                }
                for seg in timeline_data
            ]

        return result

    except Exception as e:
        logger.error(f"Error in batch state fetch for {process}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

