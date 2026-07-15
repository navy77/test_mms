import logging
import calendar
from datetime import datetime, timedelta, timezone
from typing import List, Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Path, Query, status, Request
from limiter import limiter
from database import format_result, get_ch_client, get_registered_devices as fetch_registered_devices
from models import DeviceResponse, DailyDeviceResponse, MonthlyDeviceResponse, DeviceSegment, DeviceStatusCountResponse

logger = logging.getLogger("RESTBackend.Routers.Device")
router = APIRouter(prefix="/api/v1/device", tags=["Device"])

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
    return fetch_registered_devices(process)

def resolve_devices(client, process: str, devices: Optional[str]) -> List[str]:
    """Return requested devices, or every registered device when none are supplied."""
    requested = [item.strip() for item in (devices or "").split(",")]
    device_list = [item for item in requested if item]
    if not device_list:
        device_list = get_registered_devices(client, process)
    return list(dict.fromkeys(device_list))

def get_initial_devices_batch(client, process: str, start_time: datetime, devices: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """
    Query the latest device status of all devices (or specified devices) before start_time in a single query.
    Returns a dictionary mapping device_name -> {"status": status, "created_at": datetime}.
    """
    try:
        device_filter = ""
        parameters = {"process": process, "start_time": start_time}
        if devices:
            device_filter = "AND device IN %(devices)s"
            parameters["devices"] = devices

        query = f"""
            SELECT device, status, created_at FROM device_tb
            WHERE process = %(process)s
              {device_filter}
              AND created_at < %(start_time)s
            ORDER BY created_at DESC
            LIMIT 1 BY device
        """
        result = client.query(query, parameters=parameters)
        return {row[0]: {"status": row[1], "created_at": row[2]} for row in result.result_rows}
    except Exception as e:
        logger.warning(f"Error batch fetching initial device statuses for process '{process}': {e}")
        return {}

def calculate_device_ratio(
    records: List[Dict[str, Any]], 
    start_time: datetime, 
    end_time: datetime,
    initial_status: Optional[Dict[str, Any]],
    device: str
) -> List[DeviceSegment]:
    """
    Implements the exact device status ratio calculation logic in pure Python.
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
                DeviceSegment(
                    status=status_name,
                    duration=duration,
                    ratio=ratio
                )
            )
    else:
        results = [DeviceSegment(status="no data", duration=0.0, ratio=0.0)]
        
    return results

def group_device_by_device(
    records: List[Dict[str, Any]],
    devices: List[str],
    start_time: datetime,
    end_time: datetime,
    initial_statuses: Dict[str, Dict[str, Any]]
) -> List[DeviceResponse]:
    """
    Groups current device status records by device and calculates status ratio segments.
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
        segments = calculate_device_ratio(dev_records, start_time, end_time, init_status, dev)
        results.append(
            DeviceResponse(
                device=dev,
                data=segments
            )
        )
    return results

def group_device_by_prod_date(
    records: List[Dict[str, Any]],
    devices: List[str],
    start_date,
    end_date,
    initial_statuses: Dict[str, Dict[str, Any]]
) -> List[DailyDeviceResponse]:
    """
    Groups device status records by day (production date) and device, computing status ratio segments.
    Carries forward device status from day to day.
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
            day_records.sort(key=lambda x: x.get("created_at") if isinstance(x.get("created_at"), datetime) else datetime.fromisoformat(x.get("created_at")))
            
            init_status = {"status": active_statuses[dev]} if active_statuses[dev] else None
            
            if d < current_prod_date:
                segments = calculate_device_ratio(day_records, day_start, day_end, init_status, dev)
            elif d == current_prod_date:
                segments = calculate_device_ratio(day_records, day_start, now, init_status, dev)
            else:
                segments = []
                
            results.append(
                DailyDeviceResponse(
                    date=d_str,
                    device=dev,
                    data=segments
                )
            )
            
            if day_records:
                active_statuses[dev] = day_records[-1].get("status", "unknown")
                
    return results

def group_device_by_month(
    records: List[Dict[str, Any]],
    month_str: str,
    devices: List[str],
    start_time: datetime,
    end_time: datetime,
    initial_statuses: Dict[str, Dict[str, Any]]
) -> List[MonthlyDeviceResponse]:
    """
    Groups device status records by device for the entire month, calculating status ratio segments.
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
        segments = calculate_device_ratio(dev_records, start_time, end_time, init_status, dev)
        results.append(
            MonthlyDeviceResponse(
                month=month_str,
                device=dev,
                data=segments
            )
        )
    return results

# 1. Currently Endpoints
@router.get("/currently/status/{process}", response_model=DeviceStatusCountResponse)
@limiter.limit("20/minute")
def get_currently_process_status(
    request: Request,
    process: str = Path(..., description="The process identifier")
):
    """
    Get the count of devices in each status (online, offline, no data) currently for the given process.
    """
    client = get_ch_client()
    try:
        # 1. Get all registered devices for this process
        registered_devices = get_registered_devices(client, process)
        if not registered_devices:
            return DeviceStatusCountResponse(
                process=process,
                online=0,
                offline=0,
                communication_fail=0,
                total=0
            )
            
        # 2. Get the latest status of each device in the process
        query = """
            SELECT device, status,modbus FROM device_tb
            WHERE process = %(process)s
            ORDER BY created_at DESC
            LIMIT 1 BY device
        """
        result = client.query(query, parameters={"process": process})
        latest_statuses = {row[0]: (row[1], row[2]) for row in result.result_rows}
        # 3. Count statuses
        online_count = 0
        offline_count = 0
        communication_fail = 0
        
        for dev in registered_devices:
            dev_info = latest_statuses.get(dev)
            if dev_info is None:
                offline_count += 1
            else:
                stat, modbus = dev_info
                if str(modbus) == "0" or modbus == 0:
                    communication_fail += 1
                elif stat.lower() == "online":
                    online_count += 1
                else:
                    offline_count += 1
                
        return DeviceStatusCountResponse(
            process=process,
            online=online_count,
            offline=offline_count,
            communication_fail=communication_fail,
            total=len(registered_devices)
        )
    except Exception as e:
        logger.error(f"Error counting current device statuses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/currently/{process}", response_model=List[DeviceResponse])
@limiter.limit("20/minute")
def get_currently_process(
    request: Request,
    process: str = Path(..., description="The process identifier"),
    devices: Optional[str] = Query(None, description="Optional comma-separated devices; omit for all devices."),
):
    """
    Get current device status segments for all devices in a process from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching current device status for process '{process}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        device_list = resolve_devices(client, process, devices)
        if not device_list:
            return []
        initial_statuses = get_initial_devices_batch(client, process, start_time, device_list)
        
        query = """
            SELECT process, device, status, created_at
            FROM device_tb
            WHERE process = %(process)s
              AND device IN %(devices)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "devices": device_list,
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
            
        return group_device_by_device(records, device_list, start_time, now, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching current process device statuses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def get_currently_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get current device status segments for a specific device from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching current device status for device '{process}/{device}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        initial_statuses = get_initial_devices_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM device_tb
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
            
        res = group_device_by_device(records, [device], start_time, now, initial_statuses)
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
        logger.error(f"Error fetching current device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 2. Daily Endpoints
@router.get("/daily/{process}", response_model=List[DailyDeviceResponse])
@limiter.limit("20/minute")
def get_daily_process(
    request: Request,
    process: str = Path(..., description="The process identifier"),
    devices: Optional[str] = Query(None, description="Optional comma-separated devices; omit for all devices."),
):
    """
    Get daily device status segments for all devices in a process for the current production month.
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
    
    logger.info(f"Fetching daily device status for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        device_list = resolve_devices(client, process, devices)
        if not device_list:
            return []
        initial_statuses = get_initial_devices_batch(client, process, start_time, device_list)
        
        query = """
            SELECT process, device, status, created_at
            FROM device_tb
            WHERE process = %(process)s
              AND device IN %(devices)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "devices": device_list,
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
            
        return group_device_by_prod_date(records, device_list, start_date, end_date, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily process device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def get_daily_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get daily device status segments for a specific device for the current production month.
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
    
    logger.info(f"Fetching daily device status for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        initial_statuses = get_initial_devices_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM device_tb
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
            
        return group_device_by_prod_date(records, [device], start_date, end_date, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# 3. Monthly Endpoints
@router.get("/monthly/{year}/{month}/{process}", response_model=List[MonthlyDeviceResponse])
@limiter.limit("20/minute")
def get_monthly_process(
    request: Request,
    year: int = Path(..., description="The query year (e.g. 2026)", ge=2000),
    month: int = Path(..., description="The query month (1-12)", ge=1, le=12),
    process: str = Path(..., description="The process identifier"),
    devices: Optional[str] = Query(None, description="Optional comma-separated devices; omit for all devices."),
):
    """
    Get device status segments for all devices in a process for a specific month.
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
        
    logger.info(f"Fetching monthly device status for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        device_list = resolve_devices(client, process, devices)
        if not device_list:
            return []
        initial_statuses = get_initial_devices_batch(client, process, start_time, device_list)
        
        query = """
            SELECT process, device, status, created_at
            FROM device_tb
            WHERE process = %(process)s
              AND device IN %(devices)s
              AND created_at >= %(start_time)s
              AND created_at < %(end_time)s
            ORDER BY created_at ASC
        """
        result = client.query(
            query,
            parameters={
                "process": process,
                "devices": device_list,
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
            
        return group_device_by_month(records, f"{year}-{month:02d}", device_list, start_time, end_time, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly process device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def get_monthly_device(
    year: int = Path(..., description="The query year (e.g. 2026)", ge=2000),
    month: int = Path(..., description="The query month (1-12)", ge=1, le=12),
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get device status segments for a specific device in a process for a specific month.
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
        
    logger.info(f"Fetching monthly device status for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        initial_statuses = get_initial_devices_batch(client, process, start_time, [device])
        
        query = """
            SELECT process, device, status, created_at
            FROM device_tb
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
            
        return group_device_by_month(records, f"{year}-{month:02d}", [device], start_time, end_time, initial_statuses)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

