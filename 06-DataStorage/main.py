from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import clickhouse_connect
import pandas as pd
from prefect import flow, get_run_logger, task
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


TZ_BANGKOK = ZoneInfo("Asia/Bangkok")
DEFAULT_RECORD_PERIOD_MINUTES = 60
OUTPUT_TABLE = os.getenv("DATA_STORAGE_TABLE", "data_storage_tb")
FIXED_DATA_COLUMNS = ["created_at", "process", "device"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("DataStorage")


def env_str(name: str, default: str) -> str:
    """Return a cleaned environment variable value."""
    return os.getenv(name, default).strip().strip("'\"")


def env_int(name: str, default: int) -> int:
    """Return an integer environment variable value."""
    value = env_str(name, str(default))
    return int(value)


def postgres_engine(database: str) -> Engine:
    """Create a PostgreSQL SQLAlchemy engine for the requested database."""
    host = env_str("POSTGRES_HOST", "postgres")
    port = env_int("POSTGRES_PORT", 5432)
    user = env_str("POSTGRES_USER", "postgres")
    password = env_str("POSTGRES_PASSWORD", "postgres")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    return create_engine(url, pool_pre_ping=True)


def app_db_engine() -> Engine:
    """Create the dashboard app PostgreSQL engine."""
    return postgres_engine(env_str("POSTGRES_DB", "iiot_db"))


def storage_db_engine() -> Engine:
    """Create the storage PostgreSQL engine."""
    return postgres_engine(env_str("POSTGRES_STORAGE_DB", "storage_db"))


def clickhouse_client() -> clickhouse_connect.driver.Client:
    """Create a ClickHouse client."""
    return clickhouse_connect.get_client(
        host=env_str("CLICKHOUSE_HOST", "clickhouse"),
        port=env_int("CLICKHOUSE_PORT", 8123),
        username=env_str("CLICKHOUSE_USER", "default"),
        password=env_str("CLICKHOUSE_PASSWORD", "maibok"),
        database=env_str("CLICKHOUSE_DATABASE", "default"),
    )


def quote_clickhouse_identifier(identifier: str) -> str:
    """Quote a ClickHouse identifier that came from registered metadata."""
    escaped = identifier.replace("`", "``")
    return f"`{escaped}`"


def quote_postgres_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier."""
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def postgres_type_for_series(series: pd.Series) -> str:
    """Map a pandas series to a conservative PostgreSQL column type."""
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE PRECISION"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP WITH TIME ZONE"
    return "TEXT"


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


def ensure_output_table_columns(table_name: str, data: pd.DataFrame, engine: Engine) -> None:
    """Add missing columns to an existing PostgreSQL output table."""
    if data.empty:
        return

    with engine.begin() as conn:
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
            return

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
                {"table_name": table_name},
            )
        }

        for column in data.columns:
            if column in existing_columns:
                continue
            column_type = postgres_type_for_series(data[column])
            conn.execute(
                text(
                    "ALTER TABLE "
                    f"{quote_postgres_identifier(table_name)} "
                    "ADD COLUMN "
                    f"{quote_postgres_identifier(column)} {column_type}"
                )
            )


@task(retries=3, retry_delay_seconds=30)
def get_record_period_minutes() -> int:
    """Fetch the query lookback period from project_register_tb."""
    query = """
        SELECT value
        FROM project_register_tb
        WHERE items = 'record_period'
        LIMIT 1
    """
    with app_db_engine().connect() as conn:
        value = conn.execute(text(query)).scalar()

    if value is None:
        logger.warning(
            "record_period not found; using fallback %s minutes",
            DEFAULT_RECORD_PERIOD_MINUTES,
        )
        return DEFAULT_RECORD_PERIOD_MINUTES

    try:
        record_period = int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid record_period value: {value}") from exc

    if record_period <= 0:
        raise ValueError(f"record_period must be positive, got {record_period}")

    return record_period


@task(retries=3, retry_delay_seconds=30)
def get_register_metadata() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch device and column register tables from PostgreSQL."""
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
def query_clickhouse_data(
    record_period_minutes: int,
    columns: pd.DataFrame,
) -> tuple[pd.DataFrame, datetime, datetime]:
    """Query data_tb from the current time back by record_period minutes."""
    end_time = datetime.now(TZ_BANGKOK)
    start_time = end_time - timedelta(minutes=record_period_minutes)

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
    return result, start_time, end_time


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
    if latest_data.empty:
        return 0

    engine = storage_db_engine()
    ensure_output_table_columns(OUTPUT_TABLE, latest_data, engine)

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


@flow(name="data_storage_pipeline", retries=0)
def data_storage_pipeline() -> int:
    """Run the data storage top1 aggregation pipeline."""
    run_logger = get_run_logger()
    record_period = get_record_period_minutes()
    devices, columns = get_register_metadata()
    ensure_output_table_schema(columns)
    raw_data, start_time, end_time = query_clickhouse_data(record_period, columns)
    latest_data = select_latest_by_process_device_keys(
        raw_data,
        devices,
        columns,
        record_period,
        start_time,
        end_time,
    )
    inserted_rows = write_postgres(latest_data)
    run_logger.info("Inserted %s row(s) into %s", inserted_rows, OUTPUT_TABLE)
    return inserted_rows


if __name__ == "__main__":
    data_storage_pipeline()
