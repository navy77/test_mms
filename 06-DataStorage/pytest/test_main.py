from unittest.mock import MagicMock, patch
from datetime import datetime
import pandas as pd

from main import (
    postgres_type_for_clickhouse_type,
    select_latest_by_process_device_keys,
    write_postgres,
    get_last_stored_time_end,
    ensure_raw_table_schema,
    get_last_created_at,
    write_postgres_raw,
    log_task_retry,
    TZ_BANGKOK,
)


def test_postgres_type_for_clickhouse_type():
    # Test valid ClickHouse mappings
    assert postgres_type_for_clickhouse_type("Float32") == "DOUBLE PRECISION"
    assert postgres_type_for_clickhouse_type("Float64") == "DOUBLE PRECISION"
    assert postgres_type_for_clickhouse_type("Int32") == "BIGINT"
    assert postgres_type_for_clickhouse_type("Int64") == "BIGINT"
    assert postgres_type_for_clickhouse_type("UInt32") == "BIGINT"
    assert postgres_type_for_clickhouse_type("UInt64") == "BIGINT"
    assert postgres_type_for_clickhouse_type("Bool") == "BOOLEAN"
    assert postgres_type_for_clickhouse_type("DateTime") == "TIMESTAMP WITH TIME ZONE"
    
    # Test whitespace stripping
    assert postgres_type_for_clickhouse_type(" Float32 ") == "DOUBLE PRECISION"
    
    # Test default fallback
    assert postgres_type_for_clickhouse_type("String") == "TEXT"
    assert postgres_type_for_clickhouse_type("UnknownType") == "TEXT"


@patch("main.task_run")
@patch("main.logger")
def test_log_task_retry(mock_logger, mock_task_run):
    # Case 1: run_count is None or 1 -> no warning logged
    mock_task_run.run_count = 1
    log_task_retry("test_task")
    mock_logger.warning.assert_not_called()

    # Case 2: run_count is 3 (retry attempt #2) -> warning is logged
    mock_task_run.run_count = 3
    log_task_retry("test_task")
    mock_logger.warning.assert_called_once_with(
        "Retrying task 'test_task' (Attempt #2 of 3)..."
    )


@patch("main.storage_db_engine")
def test_get_last_stored_time_end(mock_storage_db_engine):
    mock_conn = MagicMock()
    mock_storage_db_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    # Case 1: Table does not exist -> returns None
    mock_conn.execute.return_value.scalar.side_effect = [False]
    assert get_last_stored_time_end.fn() is None

    # Case 2: Table exists, but empty (MAX(time_end) is None) -> returns None
    mock_conn.execute.return_value.scalar.side_effect = [True, None]
    assert get_last_stored_time_end.fn() is None

    # Case 3: Table exists and has max timestamp -> returns timezone-aware datetime
    dt_naive = datetime(2026, 7, 15, 12, 0, 0)
    mock_conn.execute.return_value.scalar.side_effect = [True, dt_naive]
    res = get_last_stored_time_end.fn()
    assert res is not None
    assert res.tzinfo == TZ_BANGKOK
    assert res.hour == 12


@patch("main.storage_db_engine")
def test_ensure_raw_table_schema(mock_storage_db_engine):
    mock_conn = MagicMock()
    mock_storage_db_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

    ensure_raw_table_schema.fn("dummy_raw_tb")
    mock_conn.execute.assert_called_once()
    sql_arg = mock_conn.execute.call_args[0][0].text
    assert "CREATE TABLE IF NOT EXISTS \"dummy_raw_tb\"" in sql_arg


@patch("main.storage_db_engine")
def test_get_last_created_at(mock_storage_db_engine):
    mock_conn = MagicMock()
    mock_storage_db_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    # Case 1: Table does not exist
    mock_conn.execute.return_value.scalar.side_effect = [False]
    assert get_last_created_at.fn("status_storage_tb") is None

    # Case 2: Table exists but empty
    mock_conn.execute.return_value.scalar.side_effect = [True, None]
    assert get_last_created_at.fn("status_storage_tb") is None

    # Case 3: Table exists and contains records
    dt_naive = datetime(2026, 7, 15, 13, 30, 0)
    mock_conn.execute.return_value.scalar.side_effect = [True, dt_naive]
    res = get_last_created_at.fn("status_storage_tb")
    assert res is not None
    assert res.tzinfo == TZ_BANGKOK
    assert res.minute == 30


@patch("main.storage_db_engine")
def test_write_postgres_raw(mock_storage_db_engine):
    # Case 1: Empty DataFrame returns 0 immediately
    assert write_postgres_raw.fn("status_storage_tb", pd.DataFrame()) == 0

    # Case 2: DataFrame with rows
    mock_conn = MagicMock()
    mock_storage_db_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

    df = pd.DataFrame([
        {"created_at": datetime.now(), "process": "proc_a", "device": "dev_1", "status": "online"}
    ])

    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        inserted = write_postgres_raw.fn("status_storage_tb", df)
        assert inserted == 1
        mock_to_sql.assert_called_once_with(
            "status_storage_tb",
            mock_conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000
        )


def test_select_latest_by_process_device_keys():
    # Setup mock registered devices
    devices = pd.DataFrame([
        {"process": "proc_a", "device": "dev_1"},
        {"process": "proc_a", "device": "dev_2"}
    ])

    # Setup columns register metadata
    columns = pd.DataFrame([
        {"process": "proc_a", "column_name": "model", "column_type": "String", "column_key": 1},
        {"process": "proc_a", "column_name": "data1", "column_type": "Float32", "column_key": 0},
    ])

    # Case 1: Empty raw data returns empty dataframe
    start_time = datetime(2026, 7, 15, 10, 0, tzinfo=TZ_BANGKOK)
    end_time = datetime(2026, 7, 15, 11, 0, tzinfo=TZ_BANGKOK)
    res = select_latest_by_process_device_keys.fn(pd.DataFrame(), devices, columns, 60, start_time, end_time)
    assert res.empty

    # Case 2: Multiple rows in ClickHouse -> Select latest based on group
    raw_data = pd.DataFrame([
        # Dev_1 Group 1 (model A1): first entry (older)
        {"created_at": datetime(2026, 7, 15, 10, 10, tzinfo=TZ_BANGKOK), "process": "proc_a", "device": "dev_1", "model": "A1", "data1": 10.0},
        # Dev_1 Group 1 (model A1): second entry (newer -> should be selected)
        {"created_at": datetime(2026, 7, 15, 10, 20, tzinfo=TZ_BANGKOK), "process": "proc_a", "device": "dev_1", "model": "A1", "data1": 15.0},
        # Dev_1 Group 2 (model A2): single entry (should be selected)
        {"created_at": datetime(2026, 7, 15, 10, 15, tzinfo=TZ_BANGKOK), "process": "proc_a", "device": "dev_1", "model": "A2", "data1": 20.0},
        # Dev_2 Group 1 (model B1): single entry (should be selected)
        {"created_at": datetime(2026, 7, 15, 10, 10, tzinfo=TZ_BANGKOK), "process": "proc_a", "device": "dev_2", "model": "B1", "data1": 30.0},
        # Dev_3 (Not registered -> should be ignored)
        {"created_at": datetime(2026, 7, 15, 10, 30, tzinfo=TZ_BANGKOK), "process": "proc_a", "device": "dev_3", "model": "A1", "data1": 50.0},
    ])

    res = select_latest_by_process_device_keys.fn(raw_data, devices, columns, 60, start_time, end_time)
    assert len(res) == 3
    
    # Sort output for exact assertions
    res_sorted = res.sort_values(["device", "model"]).reset_index(drop=True)
    
    # Assertions on dev_1 (model A1)
    assert res_sorted.loc[0, "device"] == "dev_1"
    assert res_sorted.loc[0, "model"] == "A1"
    assert res_sorted.loc[0, "data1"] == 15.0 # Selected newer value
    
    # Assertions on dev_1 (model A2)
    assert res_sorted.loc[1, "device"] == "dev_1"
    assert res_sorted.loc[1, "model"] == "A2"
    assert res_sorted.loc[1, "data1"] == 20.0
    
    # Assertions on dev_2 (model B1)
    assert res_sorted.loc[2, "device"] == "dev_2"
    assert res_sorted.loc[2, "model"] == "B1"
    assert res_sorted.loc[2, "data1"] == 30.0

    # Verify metadata columns
    assert res_sorted.loc[0, "time_start"] == start_time
    assert res_sorted.loc[0, "time_end"] == end_time
    assert res_sorted.loc[0, "record_period_minutes"] == 60
    assert isinstance(res_sorted.loc[0, "stored_at"], datetime)


@patch("main.storage_db_engine")
def test_write_postgres(mock_storage_db_engine):
    # Case 1: Empty DataFrame returns 0 immediately without executing database connection
    res = write_postgres.fn(pd.DataFrame())
    assert res == 0
    mock_storage_db_engine.assert_not_called()

    # Case 2: DataFrame with data -> mock to_sql and verify execution
    mock_conn = MagicMock()
    mock_storage_db_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

    # Setup dummy data to write
    test_df = pd.DataFrame([
        {"created_at": datetime.now(), "process": "proc_a", "device": "dev_1", "data1": 10.0}
    ])

    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        inserted = write_postgres.fn(test_df)
        
        # Verify result size returned
        assert inserted == 1
        # Verify engine was requested
        mock_storage_db_engine.assert_called_once()
        # Verify pandas to_sql was called with correct parameters
        mock_to_sql.assert_called_once_with(
            "data_storage_tb", # Target output table
            mock_conn,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000
        )


@patch("main.clickhouse_client")
@patch("main.logger")
def test_clickhouse_clean_partition_pipeline(mock_logger, mock_clickhouse_client):
    mock_client = MagicMock()
    mock_clickhouse_client.return_value = mock_client

    from main import clickhouse_clean_partition_pipeline
    clickhouse_clean_partition_pipeline.fn()

    mock_clickhouse_client.assert_called_once()
    assert mock_client.command.call_count == 4

    called_commands = [call[0][0] for call in mock_client.command.call_args_list]
    for table in ["data_tb", "status_tb", "alarm_tb", "device_tb"]:
        assert any(f"ALTER TABLE {table} DROP PARTITION" in cmd for cmd in called_commands)

