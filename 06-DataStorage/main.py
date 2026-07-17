from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import clickhouse_connect
import pandas as pd
from prefect import flow, get_run_logger, task
from prefect.runtime import task_run
from prefect.schedules import Cron
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


TZ_BANGKOK = ZoneInfo("Asia/Bangkok")
DEFAULT_RECORD_PERIOD_MINUTES = 60
OUTPUT_TABLE = os.getenv("DATA_STORAGE_TABLE", "data_storage_tb")
FIXED_DATA_COLUMNS = ["created_at", "process", "device"]

# Ensure the log directory exists
if os.name == "nt":
    LOG_DIR = "./log"
else:
    LOG_DIR = "/var/log/apps"

try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    LOG_DIR = "./log"
    os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "datastorage.log")

# Setup logging handlers
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger = logging.getLogger("DataStorage")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def log_task_retry(task_name: str) -> None:
    """Log a warning if the task is currently retrying."""
    try:
        run_count = task_run.run_count
    except Exception:
        run_count = 1

    if run_count and run_count > 1:
        msg = f"Retrying task '{task_name}' (Attempt #{run_count - 1} of 3)..."
        # Always write to file log first
        logger.warning(msg)
        try:
            run_logger = get_run_logger()
            run_logger.warning(msg)
        except Exception:
            pass


def postgres_engine(database: str) -> Engine:
    """Create a PostgreSQL SQLAlchemy engine for the requested database."""
    host = os.getenv("POSTGRES_HOST", "postgres").strip().strip("'\"")
    port = int(os.getenv("POSTGRES_PORT", 5432))
    user = os.getenv("POSTGRES_USER", "postgres").strip().strip("'\"")
    password = os.getenv("POSTGRES_PASSWORD", "postgres").strip().strip("'\"")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    return create_engine(url, pool_pre_ping=True)


def app_db_engine() -> Engine:
    """Create the dashboard app PostgreSQL engine."""
    return postgres_engine(os.getenv("POSTGRES_DB", "iiot_db"))


def storage_db_engine() -> Engine:
    """Create the storage PostgreSQL engine."""
    return postgres_engine(os.getenv("POSTGRES_STORAGE_DB", "storage_db"))


def clickhouse_client() -> clickhouse_connect.driver.Client:
    """Create a ClickHouse client."""
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse").strip().strip("'\""),
        port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
        username=os.getenv("CLICKHOUSE_USER", "default").strip().strip("'\""),
        password=os.getenv("CLICKHOUSE_PASSWORD", "maibok").strip().strip("'\""),
        database=os.getenv("CLICKHOUSE_DATABASE", "default").strip().strip("'\""),
    )


def quote_clickhouse_identifier(identifier: str) -> str:
    """Quote a ClickHouse identifier that came from registered metadata."""
    escaped = identifier.replace("`", "``")
    return f"`{escaped}`"


def quote_postgres_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier."""
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def postgres_type_for_clickhouse_type(column_type: str) -> str:
    """Map a registered ClickHouse type to a PostgreSQL column type."""
    normalized_type = column_type.strip()
    if normalized_type in {"Float32", "Float64"}:
        return "DOUBLE PRECISION"
    if normalized_type in {"Int32", "Int64", "UInt32", "UInt64"}:
        return "BIGINT"
    if normalized_type == "Bool":
        return "BOOLEAN"
    if normalized_type == "DateTime":
        return "TIMESTAMP WITH TIME ZONE"
    return "TEXT"


@task(retries=3, retry_delay_seconds=30)
def ensure_output_table_schema(columns: pd.DataFrame) -> None:
    """Create or evolve the storage output table from registered columns."""
    log_task_retry("ensure_output_table_schema")
    base_columns = {
        "created_at": "TIMESTAMP WITH TIME ZONE",
        "process": "TEXT",
        "device": "TEXT",
        "time_start": "TIMESTAMP WITH TIME ZONE",
        "time_end": "TIMESTAMP WITH TIME ZONE",
        "record_period_minutes": "BIGINT",
        "stored_at": "TIMESTAMP WITH TIME ZONE",
    }
    dynamic_columns = {
        row["column_name"]: postgres_type_for_clickhouse_type(row["column_type"])
        for _, row in columns.iterrows()
        if pd.notna(row["column_name"])
    }
    table_columns = {**base_columns, **dynamic_columns}

    engine = storage_db_engine()
    with engine.begin() as conn:
        column_definitions = ",\n".join(
            f"            {quote_postgres_identifier(name)} {column_type}"
            for name, column_type in table_columns.items()
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_postgres_identifier(OUTPUT_TABLE)} (
{column_definitions}
                )
                """
            )
        )

        existing_columns = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                    """
                ),
                {"table_name": OUTPUT_TABLE},
            )
        }

        for column_name, column_type in table_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(
                text(
                    "ALTER TABLE "
                    f"{quote_postgres_identifier(OUTPUT_TABLE)} "
                    "ADD COLUMN "
                    f"{quote_postgres_identifier(column_name)} {column_type}"
                )
            )


@task(retries=3, retry_delay_seconds=30)
def get_register_metadata() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch device and column register tables from PostgreSQL."""
    log_task_retry("get_register_metadata")
    with app_db_engine().connect() as conn:
        devices = pd.read_sql(
            "SELECT process, device FROM device_register_tb",
            conn,
        )
        columns = pd.read_sql(
            """
            SELECT process, column_name, column_type, column_key
            FROM columns_register_tb
            """,
            conn,
        )

    return devices, columns


@task(retries=3, retry_delay_seconds=30)
def get_last_stored_time_end() -> datetime | None:
    """Fetch the latest time_end from the output table in storage PostgreSQL."""
    log_task_retry("get_last_stored_time_end")
    engine = storage_db_engine()
    with engine.connect() as conn:
        table_exists = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                )
                """
            ),
            {"table_name": OUTPUT_TABLE},
        ).scalar()

        if not table_exists:
            return None

        query = f"SELECT MAX(time_end) FROM {quote_postgres_identifier(OUTPUT_TABLE)}"
        val = conn.execute(text(query)).scalar()
        if val is not None:
            if val.tzinfo is None:
                val = val.replace(tzinfo=TZ_BANGKOK)
            return val
    return None


@task(retries=3, retry_delay_seconds=30)
def query_clickhouse_data(
    start_time: datetime,
    end_time: datetime,
    columns: pd.DataFrame,
) -> pd.DataFrame:
    """Query data_tb from the start time to the end time."""
    log_task_retry("query_clickhouse_data")
    dynamic_columns = sorted(columns["column_name"].dropna().unique().tolist())
    select_columns = FIXED_DATA_COLUMNS + dynamic_columns
    select_sql = ", ".join(quote_clickhouse_identifier(col) for col in select_columns)

    query = f"""
        SELECT {select_sql}
        FROM data_tb
        WHERE created_at >= %(start_time)s
          AND created_at <= %(end_time)s
        ORDER BY created_at ASC
    """

    client = clickhouse_client()
    result = client.query_df(
        query,
        parameters={
            "start_time": start_time.replace(tzinfo=None),
            "end_time": end_time.replace(tzinfo=None),
        },
    )
    return result


@task
def select_latest_by_process_device_keys(
    raw_data: pd.DataFrame,
    devices: pd.DataFrame,
    columns: pd.DataFrame,
    record_period_minutes: int,
    start_time: datetime,
    end_time: datetime,
) -> pd.DataFrame:
    """Select the latest row per process/device/key-columns group."""
    if raw_data.empty:
        return pd.DataFrame()

    data = raw_data.merge(devices, on=["process", "device"], how="inner")
    if data.empty:
        return pd.DataFrame()

    latest_frames: list[pd.DataFrame] = []
    data["created_at"] = pd.to_datetime(data["created_at"])

    for process, process_data in data.groupby("process", sort=True):
        process_columns = columns[columns["process"] == process]
        key_columns = process_columns.loc[
            process_columns["column_key"].astype(bool), "column_name"
        ].tolist()
        key_columns = [col for col in key_columns if col in process_data.columns]
        group_columns = ["process", "device"] + key_columns

        latest = (
            process_data.sort_values("created_at")
            .groupby(group_columns, dropna=False, as_index=False)
            .tail(1)
        )
        latest_frames.append(latest)

    if not latest_frames:
        return pd.DataFrame()

    latest_data = pd.concat(latest_frames, ignore_index=True)
    latest_data["time_start"] = start_time
    latest_data["time_end"] = end_time
    latest_data["record_period_minutes"] = record_period_minutes
    latest_data["stored_at"] = datetime.now(TZ_BANGKOK)
    latest_data = latest_data.sort_values(["process", "device", "created_at"])
    return latest_data.reset_index(drop=True)


@task(retries=3, retry_delay_seconds=30)
def write_postgres(latest_data: pd.DataFrame) -> int:
    """Append latest rows into the storage PostgreSQL table."""
    log_task_retry("write_postgres")
    if latest_data.empty:
        return 0

    engine = storage_db_engine()
    with engine.begin() as conn:
        latest_data.to_sql(
            OUTPUT_TABLE,
            conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )
    return len(latest_data)


@task(retries=3, retry_delay_seconds=30)
def ensure_raw_table_schema(table_name: str) -> None:
    """Create the status or alarm storage table if it does not exist."""
    log_task_retry("ensure_raw_table_schema")
    engine = storage_db_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {quote_postgres_identifier(table_name)} (
                    created_at TIMESTAMP WITH TIME ZONE,
                    process TEXT,
                    device TEXT,
                    status TEXT,
                    stored_at TIMESTAMP WITH TIME ZONE
                )
                """
            )
        )


@task(retries=3, retry_delay_seconds=30)
def get_last_created_at(table_name: str) -> datetime | None:
    """Fetch the latest created_at from the specified table in storage PostgreSQL."""
    log_task_retry("get_last_created_at")
    engine = storage_db_engine()
    with engine.connect() as conn:
        table_exists = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar()

        if not table_exists:
            return None

        query = f"SELECT MAX(created_at) FROM {quote_postgres_identifier(table_name)}"
        val = conn.execute(text(query)).scalar()
        if val is not None:
            if val.tzinfo is None:
                val = val.replace(tzinfo=TZ_BANGKOK)
            return val
    return None


@task(retries=3, retry_delay_seconds=30)
def query_clickhouse_raw(
    clickhouse_table: str,
    start_time: datetime,
    end_time: datetime,
) -> pd.DataFrame:
    """Query created_at, process, device, status from ClickHouse."""
    log_task_retry("query_clickhouse_raw")
    query = f"""
        SELECT created_at, process, device, status
        FROM {quote_clickhouse_identifier(clickhouse_table)}
        WHERE created_at >= %(start_time)s
          AND created_at <= %(end_time)s
        ORDER BY created_at ASC
    """
    client = clickhouse_client()
    result = client.query_df(
        query,
        parameters={
            "start_time": start_time.replace(tzinfo=None),
            "end_time": end_time.replace(tzinfo=None),
        },
    )
    return result


@task(retries=3, retry_delay_seconds=30)
def write_postgres_raw(table_name: str, df: pd.DataFrame) -> int:
    """Append raw logs into the storage PostgreSQL table."""
    log_task_retry("write_postgres_raw")
    if df.empty:
        return 0

    df = df.copy()
    df["stored_at"] = datetime.now(TZ_BANGKOK)

    engine = storage_db_engine()
    with engine.begin() as conn:
        df.to_sql(
            table_name,
            conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )
    return len(df)


@flow(name="data_storage_pipeline", retries=0)
def data_storage_pipeline() -> int:
    """Run the data storage top1 aggregation pipeline."""
    record_period = 60

    devices, columns = get_register_metadata()
    ensure_output_table_schema(columns)

    end_time = datetime.now(TZ_BANGKOK)
    last_time = get_last_stored_time_end()

    if last_time is not None:
        if last_time >= end_time:
            logger.info("Database is already up to date. Skipping aggregation.")
            return 0
        start_time = last_time
        logger.info("Found last run time: %s. Catching up from that point.", start_time)
    else:
        start_time = end_time - timedelta(minutes=record_period)
        logger.info("No prior run history found. Starting lookup from %s.", start_time)

    raw_data = query_clickhouse_data(start_time, end_time, columns)
    actual_period_minutes = int((end_time - start_time).total_seconds() / 60)

    latest_data = select_latest_by_process_device_keys(
        raw_data,
        devices,
        columns,
        actual_period_minutes,
        start_time,
        end_time,
    )
    inserted_rows = write_postgres(latest_data)
    logger.info("Inserted %s row(s) into %s", inserted_rows, OUTPUT_TABLE)
    return inserted_rows


@flow(name="status_storage_pipeline", retries=0)
def status_storage_pipeline() -> int:
    """Run the status storage log forwarding pipeline."""
    table_name = "status_storage_tb"
    ch_table = "status_tb"
    lookback_minutes = 60

    ensure_raw_table_schema(table_name)
    end_time = datetime.now(TZ_BANGKOK)
    last_time = get_last_created_at(table_name)

    if last_time is not None:
        max_lookback = timedelta(days=1)
        start_time = max(last_time, end_time - max_lookback)
        if start_time >= end_time:
            logger.info("Status log is up to date.")
            return 0
        logger.info("Found last status log: %s. Catching up.", start_time)
    else:
        start_time = end_time - timedelta(minutes=lookback_minutes)
        logger.info("No prior status log found. Starting lookup from %s.", start_time)

    raw_data = query_clickhouse_raw(ch_table, start_time, end_time)
    inserted_rows = write_postgres_raw(table_name, raw_data)
    logger.info("Inserted %s raw status row(s) into %s", inserted_rows, table_name)
    return inserted_rows


@flow(name="alarm_storage_pipeline", retries=0)
def alarm_storage_pipeline() -> int:
    """Run the alarm storage log forwarding pipeline."""
    table_name = "alarm_storage_tb"
    ch_table = "alarm_tb"
    lookback_minutes = 60

    ensure_raw_table_schema(table_name)
    end_time = datetime.now(TZ_BANGKOK)
    last_time = get_last_created_at(table_name)

    if last_time is not None:
        max_lookback = timedelta(days=1)
        start_time = max(last_time, end_time - max_lookback)
        if start_time >= end_time:
            logger.info("Alarm log is up to date.")
            return 0
        logger.info("Found last alarm log: %s. Catching up.", start_time)
    else:
        start_time = end_time - timedelta(minutes=lookback_minutes)
        logger.info("No prior alarm log found. Starting lookup from %s.", start_time)

    raw_data = query_clickhouse_raw(ch_table, start_time, end_time)
    inserted_rows = write_postgres_raw(table_name, raw_data)
    logger.info("Inserted %s raw alarm row(s) into %s", inserted_rows, table_name)
    return inserted_rows


@flow(name="clickhouse_clean_partition_pipeline", retries=0)
def clickhouse_clean_partition_pipeline() -> None:
    """Drop ClickHouse monthly partitions older than 2 months (keep last month and current month)."""
    logger.info("Starting ClickHouse partition cleanup...")
    client = clickhouse_client()

    now = datetime.now(TZ_BANGKOK)
    first_day_this_month = now.replace(day=1)
    two_months_ago = (first_day_this_month - timedelta(days=20)).replace(day=1)
    partition_key = two_months_ago.strftime("%Y%m")

    logger.info("Target partition to delete: %s", partition_key)

    tables = ["data_tb", "status_tb", "alarm_tb", "device_tb"]
    for table in tables:
        try:
            logger.info("Dropping partition %s from table %s...", partition_key, table)
            client.command(f"ALTER TABLE {table} DROP PARTITION '{partition_key}'")
            logger.info("Successfully dropped partition %s from table %s.", partition_key, table)
        except Exception as e:
            logger.warning("Failed to drop partition %s from table %s: %s", partition_key, table, e)


if __name__ == "__main__":
    from prefect import serve

    dep_data = data_storage_pipeline.to_deployment(
        name="pipeline_data",
        schedule=Cron("1 * * * *", timezone="Asia/Bangkok"),
    )
    dep_status = status_storage_pipeline.to_deployment(
        name="pipeline_status",
        schedule=Cron("1 * * * *", timezone="Asia/Bangkok"),
    )
    dep_alarm = alarm_storage_pipeline.to_deployment(
        name="pipeline_alarm",
        schedule=Cron("1 * * * *", timezone="Asia/Bangkok"),
    )
    dep_cleanup = clickhouse_clean_partition_pipeline.to_deployment(
        name="pipeline_cleanup",
        schedule=Cron("0 1 1 * *", timezone="Asia/Bangkok"),
    )
    serve(dep_data, dep_status, dep_alarm, dep_cleanup)

