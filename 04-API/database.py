import os
import logging
from fastapi import HTTPException, status
import clickhouse_connect
import psycopg2

logger = logging.getLogger("RESTBackend.Database")

_ch_client = None

def get_ch_client():
    global _ch_client
    if _ch_client is not None:
        return _ch_client

    host = os.getenv("CLICKHOUSE_HOST", "clickhouse").strip().strip("'\"")
    port = int(os.getenv("CLICKHOUSE_PORT", 8123))
    user = os.getenv("CLICKHOUSE_USER", "default").strip().strip("'\"")
    password = os.getenv("CLICKHOUSE_PASSWORD", "maibok").strip().strip("'\"")
    database = os.getenv("CLICKHOUSE_DATABASE", "default").strip().strip("'\"")
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
        logger.error(f"Failed to connect to ClickHouse: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection error: {e}"
        )


def get_registered_devices(process: str) -> list[str]:
    """Fetch registered devices for a process from the PostgreSQL app database."""
    connection = None
    try:
        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres").strip().strip("'\""),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            user=os.getenv("POSTGRES_USER", "postgres").strip().strip("'\""),
            password=os.getenv("POSTGRES_PASSWORD", "postgres").strip().strip("'\""),
            dbname=os.getenv("POSTGRES_DB", "iiot_db").strip().strip("'\""),
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT device FROM device_register_tb WHERE process = %s ORDER BY device",
                (process,),
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception as exc:
        logger.warning("Error querying PostgreSQL registered devices for '%s': %s", process, exc)
        return []
    finally:
        if connection is not None:
            connection.close()


def get_registered_columns(process: str) -> list[str]:
    """Fetch registered data columns for a process from PostgreSQL."""
    connection = None
    try:
        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres").strip().strip("'\""),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            user=os.getenv("POSTGRES_USER", "postgres").strip().strip("'\""),
            password=os.getenv("POSTGRES_PASSWORD", "postgres").strip().strip("'\""),
            dbname=os.getenv("POSTGRES_DB", "iiot_db").strip().strip("'\""),
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM columns_register_tb WHERE process = %s ORDER BY column_name",
                (process,),
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception as exc:
        logger.warning("Error querying PostgreSQL registered columns for '%s': %s", process, exc)
        return []
    finally:
        if connection is not None:
            connection.close()


# Helper to format ClickHouse results into list of dicts
def format_result(result):
    if not result or not result.result_rows:
        return []
    return [dict(zip(result.column_names, row)) for row in result.result_rows]
