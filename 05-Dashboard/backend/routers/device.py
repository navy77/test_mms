import logging
from typing import List
from fastapi import APIRouter, HTTPException, Path, status, Depends
from database import get_ch_client, get_clickhouse_client
from models import DeviceStatusCountResponse

logger = logging.getLogger("DashboardBackend.Device")

router = APIRouter(prefix="/api/v1/device", tags=["Device"])


def get_registered_devices(postgres_client, process: str) -> List[str]:
    """
    Retrieve registered device names for the given process from PostgreSQL device_register_tb.
    """
    try:
        query = "SELECT device FROM device_register_tb WHERE process = %(process)s"
        result = postgres_client.query(query, parameters={"process": process})
        return [row[0] for row in result.result_rows]
    except Exception as e:
        logger.warning(
            f"Error querying PostgreSQL device_register_tb for process '{process}': {e}"
        )
        return []


@router.get("/currently/status/{process}", response_model=DeviceStatusCountResponse)
def get_currently_process_status(
    process: str = Path(..., description="The process identifier"),
    client=Depends(get_ch_client),
):
    """
    Get the count of devices in each status (online, offline, no data) currently for the given process.
    """
    try:
        # 1. Get all registered devices for this process from PostgreSQL
        registered_devices = get_registered_devices(client, process)
        if not registered_devices:
            return DeviceStatusCountResponse(
                process=process, online=0, offline=0, communication_fail=0, total=0
            )

        # 2. Get the latest status of each device in the process from ClickHouse
        ch_client = get_clickhouse_client()
        query = """
            SELECT device, status, modbus FROM device_tb
            WHERE process = %(process)s
            ORDER BY created_at DESC
            LIMIT 1 BY device
        """
        result = ch_client.query(query, parameters={"process": process})
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
            total=len(registered_devices),
        )
    except Exception as e:
        logger.error(f"Error counting current device statuses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
