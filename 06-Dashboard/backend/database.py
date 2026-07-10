import os
import logging
from fastapi import HTTPException, status
import clickhouse_connect

logger = logging.getLogger("DashboardBackend.Database")

_ch_client = None

def get_ch_client():
    global _ch_client
    if _ch_client is not None:
        try:
            _ch_client.command("SELECT 1")
            return _ch_client
        except Exception:
            logger.info("Clickhouse client connection lost in DashboardBackend, reconnecting...")
            _ch_client = None

    host = os.getenv("CLICKHOUSE_HOST", "192.168.0.191").strip().strip("'\"")
    port = int(os.getenv("CLICKHOUSE_PORT", 8123))
    user = os.getenv("CLICKHOUSE_USER", "default").strip().strip("'\"")
    password = os.getenv("CLICKHOUSE_PASSWORD", "maibok").strip().strip("'\"")
    database = os.getenv("CLICKHOUSE_CONFIG_DATABASE", "configdb").strip().strip("'\"")
    try:
        _ch_client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=user,
            password=password,
            database=database
        )
        return _ch_client
    except Exception as e:
        if host not in ("127.0.0.1", "localhost"):
            logger.info(f"Failed to connect to ClickHouse at '{host}'. Trying fallback to '127.0.0.1'...")
            try:
                _ch_client = clickhouse_connect.get_client(
                    host="127.0.0.1",
                    port=port,
                    username=user,
                    password=password,
                    database=database
                )
                return _ch_client
            except Exception as inner_e:
                logger.error(f"Fallback connection to 127.0.0.1 also failed: {inner_e}")
        logger.error(f"Failed to connect to ClickHouse: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {e}"
        )

# Helper to format ClickHouse results into list of dicts
def format_result(result):
    if not result or not result.result_rows:
        return []
    return [dict(zip(result.column_names, row)) for row in result.result_rows]
