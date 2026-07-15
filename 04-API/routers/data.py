import logging
import calendar
from datetime import datetime, timedelta, timezone
from typing import List, Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Path, Query, status, Request
from limiter import limiter
from database import (
    format_result,
    get_ch_client,
    get_registered_columns as fetch_registered_columns,
    get_registered_devices as fetch_registered_devices,
)
from models import DataResponse, DailyDataResponse, MonthlyDataResponse

logger = logging.getLogger("RESTBackend.Routers.Data")
router = APIRouter(prefix="/api/v1/data", tags=["Data"])

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

def get_registered_columns(client, process: str) -> List[str]:
    """
    Retrieve registered column names for the given process from columns_register_tb.
    Only keep columns that exist in data_tb: data1, data2, data3, data4, data5.
    If no columns are found, default to [].
    """
    valid_cols = {"data1", "data2", "data3", "data4", "data5"}
    return [column for column in fetch_registered_columns(process) if column in valid_cols]

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

def group_by_device(records: List[Dict[str, Any]]) -> List[DataResponse]:
    """
    Groups flat records by device name.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        dev = r.get("device", "unknown")
        # Format datetime objects to ISO strings for JSON serialization
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        
        if dev not in groups:
            groups[dev] = []
        groups[dev].append(r)
        
    return [DataResponse(device=dev, data=msgs) for dev, msgs in groups.items()]

def format_device_response(device: str, records: List[Dict[str, Any]]) -> DataResponse:
    """
    Formats list of records for a single device.
    """
    for r in records:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    return DataResponse(device=device, data=records)

def group_by_prod_date_and_device(
    records: List[Dict[str, Any]],
    devices: List[str],
    start_date,
    end_date
) -> List[DailyDataResponse]:
    """
    Groups records by their production date and device, filling missing dates with empty data.
    The output is sorted chronologically (ASC) from start_date to end_date.
    """
    # Build list of all dates in the range chronologically (ASC)
    date_list = []
    curr = start_date
    while curr <= end_date:
        date_list.append(curr.isoformat())
        curr += timedelta(days=1)
        
    groups = {}
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
        
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
            
        key = (prod_date_str, dev)
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
        
    results = []
    # Merge query-found devices with registered devices
    all_devices = list(set(devices + [r.get("device") for r in records if r.get("device")]))
    if not all_devices:
        all_devices = []
    all_devices.sort()
    
    # Sort chronologically (ASC) for chart rendering (1st, 2nd, ..., 31st)
    for date_str in date_list:
        for dev in all_devices:
            data_list = groups.get((date_str, dev), [])
            results.append(
                DailyDataResponse(
                    date=date_str,
                    device=dev,
                    data=data_list
                )
            )
            
    return results

def group_by_month_and_device(
    records: List[Dict[str, Any]],
    month_str: str,
    devices: List[str]
) -> List[MonthlyDataResponse]:
    """
    Groups records by month and device, returning a single latest record per device for the month.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        dev = r.get("device", "unknown")
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        if dev not in groups:
            groups[dev] = []
        groups[dev].append(r)
        
    all_devices = list(set(devices + list(groups.keys())))
    all_devices.sort()
    
    results = []
    for dev in all_devices:
        data_list = groups.get(dev, [])
        results.append(
            MonthlyDataResponse(
                month=month_str,
                device=dev,
                data=data_list
            )
        )
    return results


# 1. currently Endpoints
@router.get("/currently/{process}", response_model=List[DataResponse])
@limiter.limit("20/minute")
def get_currently_process(
    request: Request,
    process: str = Path(..., description="The process identifier"),
    devices: Optional[str] = Query(None, description="Optional comma-separated devices; omit for all devices."),
):
    """
    Get currently data for all devices in a process from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching currently data for process '{process}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        device_list = resolve_devices(client, process, devices)
        if not device_list:
            return []
        cols = get_registered_columns(client, process)
        select_cols = ["process", "device"] + cols + ["created_at"]
        select_str = ", ".join(select_cols)
        
        query = f"""
            SELECT {select_str}
            FROM data_tb
            WHERE process = %(process)s
              AND device IN %(devices)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at DESC
            LIMIT 1 BY device
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
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
        return group_by_device(records)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching currently process data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def get_currently_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get currently data for a specific device in a process from 07:00 of the current production day until now.
    """
    now = get_now_bangkok()
    start_time, end_time = get_production_day_range(now)
    
    logger.info(f"Fetching currently data for device '{process}/{device}' from {start_time} to {now}")
    client = get_ch_client()
    try:
        cols = get_registered_columns(client, process)
        select_cols = ["process", "device"] + cols + ["created_at"]
        select_str = ", ".join(select_cols)
        
        query = f"""
            SELECT {select_str}
            FROM data_tb
            WHERE process = %(process)s
              AND device = %(device)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at DESC
            LIMIT 1
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
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
        return format_device_response(device, records)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching currently device data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 2. Daily Endpoints
@router.get("/daily/{process}", response_model=List[DailyDataResponse])
@limiter.limit("20/minute")
def get_daily_process(
    request: Request,
    process: str = Path(..., description="The process identifier"),
    devices: Optional[str] = Query(None, description="Optional comma-separated devices; omit for all devices."),
):
    """
    Get daily data for all devices in a process from 07:00 of the 1st day of the current production month to the last day of the month.
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
    end_time = datetime.combine(end_date, datetime.min.time(), tzinfo=TZ_BANGKOK) + timedelta(days=1, hours=7) - timedelta(microseconds=1)
    
    logger.info(f"Fetching daily data for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        device_list = resolve_devices(client, process, devices)
        if not device_list:
            return []
        cols = get_registered_columns(client, process)
        select_cols = ["process", "device"] + cols + ["created_at"]
        select_str = ", ".join(select_cols)
        
        query = f"""
            SELECT {select_str}
            FROM data_tb
            WHERE process = %(process)s
              AND device IN %(devices)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at DESC
            LIMIT 1 BY toDate(created_at - INTERVAL 7 HOUR), device
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
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
        return group_by_prod_date_and_device(records, device_list, start_date, end_date)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily process data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

def get_daily_device(
    process: str = Path(..., description="The process identifier"),
    device: str = Path(..., description="The device identifier")
):
    """
    Get daily data for a specific device in a process from 07:00 of the 1st day of the current production month to the last day of the month.
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
    end_time = datetime.combine(end_date, datetime.min.time(), tzinfo=TZ_BANGKOK) + timedelta(days=1, hours=7) - timedelta(microseconds=1)
    
    logger.info(f"Fetching daily data for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        cols = get_registered_columns(client, process)
        select_cols = ["process", "device"] + cols + ["created_at"]
        select_str = ", ".join(select_cols)
        
        query = f"""
            SELECT {select_str}
            FROM data_tb
            WHERE process = %(process)s
              AND device = %(device)s
              AND created_at >= %(start_time)s
              AND created_at <= %(end_time)s
            ORDER BY created_at DESC
            LIMIT 1 BY toDate(created_at - INTERVAL 7 HOUR), device
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
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
        return group_by_prod_date_and_device(records, [device], start_date, end_date)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily device data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# 3. Monthly Endpoints
@router.get("/monthly/{year}/{month}/{process}", response_model=List[MonthlyDataResponse])
@limiter.limit("20/minute")
def get_monthly_process(
    request: Request,
    year: int = Path(..., description="The query year (e.g. 2026)", ge=2000),
    month: int = Path(..., description="The query month (1-12)", ge=1, le=12),
    process: str = Path(..., description="The process identifier"),
    devices: Optional[str] = Query(None, description="Optional comma-separated devices; omit for all devices."),
):
    """
    Get the single latest data record for each device in a process for a specific month.
    """
    start_time = datetime(year, month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    # Calculate next month start time
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    end_time = datetime(next_year, next_month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    logger.info(f"Fetching monthly data for process '{process}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        device_list = resolve_devices(client, process, devices)
        if not device_list:
            return []
        cols = get_registered_columns(client, process)
        select_cols = ["process", "device"] + cols + ["created_at"]
        select_str = ", ".join(select_cols)
        
        query = f"""
            SELECT {select_str}
            FROM data_tb
            WHERE process = %(process)s
              AND device IN %(devices)s
              AND created_at >= %(start_time)s
              AND created_at < %(end_time)s
            ORDER BY created_at DESC
            LIMIT 1 BY device
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
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
        return group_by_month_and_device(records, f"{year}-{month:02d}", device_list)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly process data: {e}")
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
    Get the single latest data record for a specific device in a process for a specific month.
    """
    start_time = datetime(year, month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    # Calculate next month start time
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    end_time = datetime(next_year, next_month, 1, 7, 0, 0, tzinfo=TZ_BANGKOK)
    
    logger.info(f"Fetching monthly data for device '{process}/{device}' from {start_time} to {end_time}")
    client = get_ch_client()
    try:
        cols = get_registered_columns(client, process)
        select_cols = ["process", "device"] + cols + ["created_at"]
        select_str = ", ".join(select_cols)
        
        query = f"""
            SELECT {select_str}
            FROM data_tb
            WHERE process = %(process)s
              AND device = %(device)s
              AND created_at >= %(start_time)s
              AND created_at < %(end_time)s
            ORDER BY created_at DESC
            LIMIT 1
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
        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item not found"
            )
        return group_by_month_and_device(records, f"{year}-{month:02d}", [device])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching monthly device data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
