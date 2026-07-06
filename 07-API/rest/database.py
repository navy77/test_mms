import os
import logging
from fastapi import HTTPException, status
import clickhouse_connect

logger = logging.getLogger("RESTBackend.Database")

def get_ch_client():
    host = os.getenv("CLICKHOUSE_HOST", "clickhouse").strip().strip("'\"")
    port = int(os.getenv("CLICKHOUSE_PORT", 8123))
    user = os.getenv("CLICKHOUSE_USER", "default").strip().strip("'\"")
    password = os.getenv("CLICKHOUSE_PASSWORD", "maibok").strip().strip("'\"")
    database = os.getenv("CLICKHOUSE_DATABASE", "default").strip().strip("'\"")
    try:
        return clickhouse_connect.get_client(
            host=host,
            port=port,
            username=user,
            password=password,
            database=database
        )
    except Exception as e:
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
