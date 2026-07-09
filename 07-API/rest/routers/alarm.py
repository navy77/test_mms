import os
import logging
import calendar
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import List, Any, Dict, Optional, Set, Tuple
from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import StreamingResponse
from database import get_ch_client, format_result
from models import AlarmResponse, DailyAlarmResponse, MonthlyAlarmResponse, AlarmSegment

logger = logging.getLogger("RESTBackend.Routers.Alarm")
router = APIRouter(prefix="/api/v1/alarm", tags=["Alarm"])

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

def get_initial_alarms_batch(client, process: str, start_time: datetime, devices: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """
    Query the latest alarm of all devices (or specified devices) before start_time in a single query.
    Returns a dictionary mapping device_name -> {"status": status, "created_at": datetime}.
    """
    try:
        device_filter = ""
        parameters = {"process": process, "start_time": start_time}
        if devices:
            device_filter = "AND device IN %(devices)s"
            parameters["devices"] = devices

        query = f"""
            SELECT device, status, created_at FROM alarm_tb
            WHERE process = %(process)s
              {device_filter}
              AND created_at < %(start_time)s
            ORDER BY created_at DESC
            LIMIT 1 BY device
        """
        result = client.query(query, parameters=parameters)
        return {row[0]: {"status": row[1], "created_at": row[2]} for row in result.result_rows}
    except Exception as e:
        logger.warning(f"Error batch fetching initial alarms for process '{process}': {e}")
        return {}

def calculate_alarm_ratio(
    records: List[Dict[str, Any]], 
    start_time: datetime, 
    end_time: datetime,
    initial_active_alarms: Set[str],
    device: str
) -> Tuple[List[AlarmSegment], Set[str]]:
    """
    Implements the alarm duration ratio calculation logic in Python.
    Alarms come in pairs: start event (e.g. alarm_name) and end event (e.g. alarm_name_).
    """
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=TZ_BANGKOK)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=TZ_BANGKOK)

    # 1. Parse all records in range and sort by timestamp
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

    # 2. Initialize active alarms
    active_alarms = set(initial_active_alarms)

    # 3. Create a timeline of timestamps and trace status intervals
    # We will build a list of events to process
    timeline_events = [{"time": start_time, "is_event": False}]
    for pr in parsed_records:
        timeline_events.append({"time": pr["created_at"], "is_event": True, "status": pr["status"]})
    timeline_events.append({"time": end_time, "is_event": False})

    # Sort events by time.
    timeline_events.sort(key=lambda x: x["time"])

    alarm_durations = {}
    total_duration = 0.0

    for i in range(len(timeline_events) - 1):
        t_curr = timeline_events[i]["time"]
        t_next = timeline_events[i+1]["time"]
        duration = max(0.0, (t_next - t_curr).total_seconds())
        duration = round(duration, 1)

        # Apply active alarms to this interval
        if duration > 0:
            # We filter out "no data" and "normal" to only calculate actual active alarms
            valid_alarms = [alm for alm in active_alarms if alm not in ("no data", "normal")]
            if valid_alarms:
                for alm in valid_alarms:
                    alarm_durations[alm] = alarm_durations.get(alm, 0.0) + duration
                    total_duration += duration

        # Update active_alarms state at t_next based on its event (if any)
        next_event = timeline_events[i+1]
        if next_event.get("is_event"):
            status_val = next_event["status"]
            if status_val.endswith("_"):
                # End of an alarm
                base_alarm = status_val[:-1]
                if base_alarm in active_alarms:
                    active_alarms.remove(base_alarm)
                else:
                    # The alarm started before start_time and has just ended
                    missed_duration = max(0.0, (t_next - start_time).total_seconds())
                    missed_duration = round(missed_duration, 1)
                    if missed_duration > 0:
                        alarm_durations[base_alarm] = alarm_durations.get(base_alarm, 0.0) + missed_duration
                        total_duration += missed_duration
            else:
                # Start of an alarm
                active_alarms.discard("no data")
                active_alarms.add(status_val)

    # 4. Find ratio %
    results = []
    if total_duration > 0:
        for alarm_name, duration in alarm_durations.items():
            ratio = round((duration / total_duration) * 100, 1)
            results.append(
                AlarmSegment(
                    alarm=alarm_name,
                    duration=duration,
                    ratio=ratio
                )
            )
        
    return results, active_alarms

def group_alarm_by_device(
    records: List[Dict[str, Any]],
    devices: List[str],
    start_time: datetime,
    end_time: datetime,
    initial_alarms: Dict[str, Dict[str, Any]]
) -> List[AlarmResponse]:
    """
    Groups current alarm records by device and calculates duration ratio segments.
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
        init_val = initial_alarms.get(dev)
        init_active = set()
        if init_val:
            init_status = init_val.get("status")
            if init_status and not init_status.endswith("_") and init_status != "no data" and init_status != "normal":
                init_active.add(init_status)
        else:
            if not dev_records:
                init_active.add("no data")

        segments, _ = calculate_alarm_ratio(dev_records, start_time, end_time, init_active, dev)
        results.append(
            AlarmResponse(
                device=dev,
                data=segments
            )
        )
    return results

def group_alarm_by_prod_date(
    records: List[Dict[str, Any]],
    devices: List[str],
    start_date,
    end_date,
    initial_alarms: Dict[str, Dict[str, Any]]
) -> List[DailyAlarmResponse]:
    """
    Groups alarm records by day (production date) and device, computing duration segments.
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
    
    # Track the active alarms set for each device.
    active_alarms_map = {}
    for dev in all_devices:
        init_val = initial_alarms.get(dev)
        init_active = set()
        if init_val:
            init_status = init_val.get("status")
            if init_status and not init_status.endswith("_") and init_status != "no data" and init_status != "normal":
                init_active.add(init_status)
        else:
            init_active.add("no data")
        active_alarms_map[dev] = init_active
            
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
            
            init_active = set(active_alarms_map[dev])
            
            if d < current_prod_date:
                segments, final_active = calculate_alarm_ratio(day_records, day_start, day_end, init_active, dev)
            elif d == current_prod_date:
                segments, final_active = calculate_alarm_ratio(day_records, day_start, now, init_active, dev)
            else:
                segments = []
                final_active = init_active
                
            results.append(
                DailyAlarmResponse(
                    date=d_str,
                    device=dev,
                    data=segments
                )
            )
            
            active_alarms_map[dev] = final_active
                
    return results

def group_alarm_by_month(
    records: List[Dict[str, Any]],
    month_str: str,
    devices: List[str],
    start_time: datetime,
    end_time: datetime,
    initial_alarms: Dict[str, Dict[str, Any]]
) -> List[MonthlyAlarmResponse]:
    """
    Groups alarm records by device for the entire month, calculating status ratio segments.
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
        init_val = initial_alarms.get(dev)
        init_active = set()
        if init_val:
            init_status = init_val.get("status")
            if init_status and not init_status.endswith("_") and init_status != "no data" and init_status != "normal":
                init_active.add(init_status)
        else:
            if not dev_records:
                init_active.add("no data")

        segments, _ = calculate_alarm_ratio(dev_records, start_time, end_time, init_active, dev)
        results.append(
            MonthlyAlarmResponse(
                month=month_str,
                device=dev,
                data=segments
            )
        )
    return results

# 1. Currently Endpoint
@router.get("/currently/{process}", response_model=List[AlarmResponse])
def get_currently_process(
    process: str = Path(..., description="The process identifier")
):
    """
    Get current alarm segments for all devices in a process from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching current alarm for process '{process}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        devices = get_registered_devices(client, process)
        initial_alarms = get_initial_alarms_batch(client, process, start_time, devices)
        
        query = """
            SELECT process, device, status, created_at
            FROM alarm_tb
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
        
        has_data = len(records) > 0 or len(initial_alarms) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_alarm_by_device(records, devices, start_time, now, initial_alarms)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching current process alarms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/currently/{process}/{device}", response_model=AlarmResponse)
def get_currently_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get current alarm segments for a specific device from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching current alarm for device '{process}/{device}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        initial_alarms = get_initial_alarms_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM alarm_tb
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
        
        has_data = len(records) > 0 or len(initial_alarms) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        res = group_alarm_by_device(records, [device], start_time, now, initial_alarms)
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
        logger.error(f"Error fetching current device alarms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 2. Daily Endpoints
@router.get("/daily/{process}", response_model=List[DailyAlarmResponse])
def get_daily_process(
    process: str = Path(..., description="The process identifier")
):
    """
    Get daily alarm segments for all devices in a process for the current production month.
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
    
    logger.info(f"Fetching daily alarms for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        devices = get_registered_devices(client, process)
        initial_alarms = get_initial_alarms_batch(client, process, start_time, devices)
        
        query = """
            SELECT process, device, status, created_at
            FROM alarm_tb
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
        
        has_data = len(records) > 0 or len(initial_alarms) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_alarm_by_prod_date(records, devices, start_date, end_date, initial_alarms)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily process alarms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/daily/{process}/{device}", response_model=List[DailyAlarmResponse])
def get_daily_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get daily alarm segments for a specific device for the current production month.
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
    
    logger.info(f"Fetching daily alarms for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        initial_alarms = get_initial_alarms_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM alarm_tb
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
        
        has_data = len(records) > 0 or len(initial_alarms) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_alarm_by_prod_date(records, [device], start_date, end_date, initial_alarms)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily device alarms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 3. Monthly Endpoints
@router.get("/monthly/{year}/{month}/{process}", response_model=List[MonthlyAlarmResponse])
def get_monthly_process(
    year: int = Path(..., description="The query year (e.g. 2026)", ge=2000),
    month: int = Path(..., description="The query month (1-12)", ge=1, le=12),
    process: str = Path(..., description="The process identifier")
):
    """
    Get alarm segments for all devices in a process for a specific month.
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
        
    logger.info(f"Fetching monthly alarms for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        devices = get_registered_devices(client, process)
        initial_alarms = get_initial_alarms_batch(client, process, start_time, devices)
        
        query = """
            SELECT process, device, status, created_at
            FROM alarm_tb
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
        
        has_data = len(records) > 0 or len(initial_alarms) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_alarm_by_month(records, f"{year}-{month:02d}", devices, start_time, end_time, initial_alarms)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly process alarms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/monthly/{year}/{month}/{process}/{device}", response_model=List[MonthlyAlarmResponse])
def get_monthly_device(
    year: int = Path(..., description="The query year (e.g. 2026)", ge=2000),
    month: int = Path(..., description="The query month (1-12)", ge=1, le=12),
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get alarm segments for a specific device in a process for a specific month.
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
        
    logger.info(f"Fetching monthly alarms for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        initial_alarms = get_initial_alarms_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM alarm_tb
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
        
        has_data = len(records) > 0 or len(initial_alarms) > 0
        if not has_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
            
        return group_alarm_by_month(records, f"{year}-{month:02d}", [device], start_time, end_time, initial_alarms)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly device alarms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 5. SSE currently alarm stream
@router.get("/stream/currently/{process}/{device}")
async def stream_currently_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    SSE stream yielding currently alarm ratio segments for a specific device.
    Fires every 30 seconds.
    """
    async def event_generator():
        logger.info(f"SSE currently alarm stream started for device '{process}/{device}'")
        try:
            while True:
                now = get_now_bangkok()
                start_time, end_time = get_production_day_range(now)
                client = get_ch_client()
                
                initial_alarms = get_initial_alarms_batch(client, process, start_time, [device])

                query = """
                    SELECT process, device, status, created_at
                    FROM alarm_tb
                    WHERE process = %(process)s
                      AND device = %(device)s
                      AND created_at >= %(start_time)s
                      AND created_at <= %(end_time)s
                    ORDER BY created_at ASC
                """
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: client.query(
                        query,
                        parameters={
                            "process": process,
                            "device": device,
                            "start_time": start_time,
                            "end_time": now
                        }
                    )
                )
                records = format_result(result)
                
                res = group_alarm_by_device(records, [device], start_time, now, initial_alarms)
                response_data = {}
                if res:
                    response_data = {
                        "device": res[0].device,
                        "data": [seg.dict() if hasattr(seg, "dict") else seg for seg in res[0].data]
                    }
                
                yield f"data: {json.dumps(response_data)}\n\n"
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info(f"SSE currently alarm stream cancelled for device '{process}/{device}'")
            raise
        except Exception as e:
            logger.error(f"Error in SSE currently alarm stream: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# 6. SSE daily alarm stream
@router.get("/stream/daily/{process}/{device}")
async def stream_daily_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    SSE stream yielding daily alarm ratio segments for a specific device.
    Fires every 30 seconds.
    """
    async def event_generator():
        logger.info(f"SSE daily alarm stream started for device '{process}/{device}'")
        try:
            while True:
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

                client = get_ch_client()
                initial_alarms = get_initial_alarms_batch(client, process, start_time, [device])

                query = """
                    SELECT process, device, status, created_at
                    FROM alarm_tb
                    WHERE process = %(process)s
                      AND device = %(device)s
                      AND created_at >= %(start_time)s
                      AND created_at <= %(end_time)s
                    ORDER BY created_at ASC
                """
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: client.query(
                        query,
                        parameters={
                            "process": process,
                            "device": device,
                            "start_time": start_time,
                            "end_time": end_time
                        }
                    )
                )
                records = format_result(result)
                
                daily_alarms = group_alarm_by_prod_date(records, [device], start_date, end_date, initial_alarms)
                
                response_list = []
                for d in daily_alarms:
                    response_list.append({
                        "date": d.date,
                        "device": d.device,
                        "data": [seg.dict() if hasattr(seg, "dict") else seg for seg in d.data]
                    })
                
                yield f"data: {json.dumps(response_list)}\n\n"
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info(f"SSE daily alarm stream cancelled for device '{process}/{device}'")
            raise
        except Exception as e:
            logger.error(f"Error in SSE daily alarm stream: {e}")
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

