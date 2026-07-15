import logging
import os
import re
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends, Query
from database import get_ch_client, get_clickhouse_client, format_result
from security import hash_password, verify_admin
from models import (
    UserCreate, UserUpdate, UserResponse,
    DeviceCreate, DeviceUpdate, DeviceResponse,
    ColumnCreate, ColumnBatchCreate, ColumnResponse,
    ProjectCreate, ProjectUpdate, ProjectResponse,
    StatusRegisterCreate, StatusRegisterUpdate, StatusRegisterResponse,
    AlarmRegisterCreate, AlarmRegisterUpdate, AlarmRegisterResponse
)

logger = logging.getLogger("DashboardBackend.RegisterRouter")

router = APIRouter(
    prefix="/api/v1",
    tags=["register"]
)

VALID_COLUMN_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_CLICKHOUSE_TYPES = {
    "String",
    "Float32",
    "Float64",
    "Int32",
    "Int64",
    "UInt32",
    "UInt64",
    "Bool",
    "DateTime",
}

BENTHOS_KAFKA_CLICKHOUSE_CONFIG = os.getenv(
    "BENTHOS_KAFKA_CLICKHOUSE_CONFIG",
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "02-Benthos",
            "03-KafkaClickhouse",
            "benthos.yaml",
        )
    ),
)


def validate_clickhouse_column(column: ColumnCreate):
    if not VALID_COLUMN_NAME_RE.fullmatch(column.column_name):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid column name '{column.column_name}'. Use letters, numbers, "
                "and underscores only, and do not start with a number."
            ),
        )

    if column.column_type not in ALLOWED_CLICKHOUSE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_CLICKHOUSE_TYPES))
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ClickHouse type '{column.column_type}'. Allowed types: {allowed}",
        )


def quote_clickhouse_identifier(identifier: str) -> str:
    return f"`{identifier}`"


def benthos_payload_mapping(column_name: str, column_type: str) -> str:
    if column_type == "String":
        return f'$payload.{column_name}.string().catch("")'
    if column_type == "Bool":
        return f"$payload.{column_name}.bool().catch(false)"
    if column_type == "DateTime":
        return f'$payload.{column_name}.string().catch("")'
    return f"$payload.{column_name}.number().catch(0.0)"


def render_benthos_kafka_clickhouse_config(columns: List[dict]) -> str:
    column_lines = "\n".join(f"              - {column['column_name']}" for column in columns)
    mapping_lines = ",\n".join(
        f"                {benthos_payload_mapping(column['column_name'], column['column_type'])}"
        for column in columns
    )

    return f"""logger:
  level: INFO
  format: logfmt
  add_timestamp: true
metrics:
  logger:
    push_interval: 30s
    flush_metrics: true

input:
  label: kafka_input
  kafka:
    addresses: [\"kafka:9092\"]
    topics: [\"data\", \"status\", \"alarm\"]
    consumer_group: \"benthos_clickhouse_group\"
    start_from_oldest: true
    batching:
      period: 1s
      byte_size: 100000

output:
  switch:
    cases:
      - check: meta(\"kafka_topic\") == \"status\"
        output:
          sql_insert:
            driver: clickhouse
            dsn: clickhouse://default:maibok@clickhouse:9000/default
            table: status_tb
            columns:
              - process
              - device
              - status
            args_mapping: |
              root = [
                this.process,
                this.device,
                this.payload.parse_json().catch({{\"status\": this.payload}}).status
              ]
            batching:
              count: 10000
              period: 1s

      - check: meta(\"kafka_topic\") == \"alarm\"
        output:
          sql_insert:
            driver: clickhouse
            dsn: clickhouse://default:maibok@clickhouse:9000/default
            table: alarm_tb
            columns:
              - process
              - device
              - status
            args_mapping: |
              root = [
                this.process,
                this.device,
                this.payload.parse_json().catch({{\"status\": this.payload}}).status
              ]
            batching:
              count: 10000
              period: 1s

      - check: meta(\"kafka_topic\") == \"data\"
        output:
          sql_insert:
            driver: clickhouse
            dsn: clickhouse://default:maibok@clickhouse:9000/default
            table: data_tb
            columns:
              - process
              - device
{column_lines}
            args_mapping: |
              let payload = this.payload.parse_json().catch({{}})
              root = [
                this.process,
                this.device,
{mapping_lines}
              ]
            batching:
              count: 10000
              period: 1s
"""


def regenerate_benthos_kafka_clickhouse_config(client):
    result = client.query(
        """
        SELECT process, column_name, column_type, column_key
        FROM columns_register_tb
        ORDER BY last_update ASC, process ASC, column_name ASC
        """
    )
    registered_columns = format_result(result)
    seen_column_names = set()
    data_columns = []

    for column in registered_columns:
        column_name = column["column_name"]
        if column_name in seen_column_names:
            continue
        validate_clickhouse_column(
            ColumnCreate(
                process=column["process"],
                column_name=column_name,
                column_type=column["column_type"],
                column_key=column["column_key"],
            )
        )
        seen_column_names.add(column_name)
        data_columns.append(column)

    config = render_benthos_kafka_clickhouse_config(data_columns)
    config_path = BENTHOS_KAFKA_CLICKHOUSE_CONFIG
    config_dir = os.path.dirname(config_path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)

    with open(config_path, "w", encoding="utf-8", newline="\n") as config_file:
        config_file.write(config)

    logger.info(
        "Regenerated Benthos Kafka ClickHouse config at %s with %s data column(s)",
        config_path,
        len(data_columns),
    )
    return {"path": config_path, "data_columns": len(data_columns)}


def ensure_columns_can_be_registered(columns: List[ColumnCreate], client):
    seen = set()
    for column in columns:
        validate_clickhouse_column(column)
        key = (column.process, column.column_name)
        if key in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{column.column_name}' under process '{column.process}' is duplicated in request",
            )
        seen.add(key)

    for column in columns:
        dup_check = client.query(
            "SELECT column_name FROM columns_register_tb WHERE process = %(p)s AND column_name = %(c)s",
            parameters={"p": column.process, "c": column.column_name},
        )
        if dup_check.result_rows:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{column.column_name}' under process '{column.process}' is already registered",
            )

    ch_client = get_clickhouse_client()
    return ch_client


def register_columns_in_clickhouse_and_postgres(columns: List[ColumnCreate], client):
    ch_client = ensure_columns_can_be_registered(columns, client)

    for column in columns:
        column_name = quote_clickhouse_identifier(column.column_name)
        ch_client.command(
            f"ALTER TABLE data_tb ADD COLUMN IF NOT EXISTS {column_name} {column.column_type}"
        )
        logger.info(
            "Added ClickHouse data_tb column: %s %s",
            column.column_name,
            column.column_type,
        )

    client.insert(
        "columns_register_tb",
        [
            [column.process, column.column_name, column.column_type, column.column_key]
            for column in columns
        ],
        column_names=["process", "column_name", "column_type", "column_key"],
    )


# =====================================================================
# API Endpoints
# =====================================================================

# ---------------------------------------------------------------------
# User Register Table CRUD
# ---------------------------------------------------------------------

@router.get("/users", response_model=List[UserResponse])
def get_users(client = Depends(get_ch_client)):
    logger.info("Fetching all users")
    try:
        result = client.query('SELECT last_update, "user", role FROM user_register_tb ORDER BY last_update DESC')
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_user(user_data: UserCreate, client = Depends(get_ch_client)):
    logger.info(f"Creating user: {user_data.user}")
    try:
        # Check if user already exists
        dup_check = client.query('SELECT "user" FROM user_register_tb WHERE "user" = %(u)s', parameters={'u': user_data.user})
        if dup_check.result_rows:
            raise HTTPException(status_code=400, detail=f"User '{user_data.user}' already registered")
        
        # Insert user
        client.insert(
            'user_register_tb',
            [[user_data.user, hash_password(user_data.password), user_data.role]],
            column_names=['user', 'password', 'role']
        )
        return {"message": f"User '{user_data.user}' created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/users/{username}", dependencies=[Depends(verify_admin)])
def update_user(username: str, update_data: UserUpdate, client = Depends(get_ch_client)):
    logger.info(f"Updating user: {username}")
    try:
        # Check if user exists
        check = client.query('SELECT "user" FROM user_register_tb WHERE "user" = %(u)s', parameters={'u': username})
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        
        # Update user
        client.command(
            'UPDATE user_register_tb SET password = %(pwd)s, role = %(role)s WHERE "user" = %(u)s',
            parameters={'pwd': hash_password(update_data.password), 'role': update_data.role, 'u': username}
        )
        return {"message": f"User '{username}' updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{username}", dependencies=[Depends(verify_admin)])
def delete_user(username: str, client = Depends(get_ch_client)):
    logger.info(f"Deleting user: {username}")
    try:
        # Check if user exists
        check = client.query('SELECT "user" FROM user_register_tb WHERE "user" = %(u)s', parameters={'u': username})
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        
        # Delete user
        client.command('DELETE FROM user_register_tb WHERE "user" = %(u)s', parameters={'u': username})
        return {"message": f"User '{username}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------
# Device Register Table CRUD
# ---------------------------------------------------------------------

@router.get("/devices", response_model=List[DeviceResponse])
def get_devices(client = Depends(get_ch_client)):
    logger.info("Fetching all devices")
    try:
        result = client.query("SELECT last_update, process, device FROM device_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/devices", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_device(device_data: DeviceCreate, client = Depends(get_ch_client)):
    logger.info(f"Registering device: {device_data.process}/{device_data.device}")
    try:
        # Check for duplicate
        dup_check = client.query(
            "SELECT device FROM device_register_tb WHERE process = %(p)s AND device = %(d)s",
            parameters={'p': device_data.process, 'd': device_data.device}
        )
        if dup_check.result_rows:
            raise HTTPException(status_code=400, detail=f"Device '{device_data.device}' under process '{device_data.process}' is already registered")
        
        # Insert device
        client.insert(
            'device_register_tb',
            [[device_data.process, device_data.device]],
            column_names=['process', 'device']
        )
        return {"message": f"Device '{device_data.device}' registered under process '{device_data.process}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering device: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/devices", dependencies=[Depends(verify_admin)])
def update_device(update_data: DeviceUpdate, client = Depends(get_ch_client)):
    logger.info(f"Updating device registration: {update_data.old_process}/{update_data.old_device} -> {update_data.new_process}/{update_data.new_device}")
    try:
        # Check if original device exists
        check = client.query(
            "SELECT device FROM device_register_tb WHERE process = %(op)s AND device = %(od)s",
            parameters={'op': update_data.old_process, 'od': update_data.old_device}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Device '{update_data.old_device}' under process '{update_data.old_process}' not found")
        
        # Check if the new name would collide with another existing entry (if they changed the name)
        if (update_data.old_process != update_data.new_process) or (update_data.old_device != update_data.new_device):
            dup_check = client.query(
                "SELECT device FROM device_register_tb WHERE process = %(np)s AND device = %(nd)s",
                parameters={'np': update_data.new_process, 'nd': update_data.new_device}
            )
            if dup_check.result_rows:
                raise HTTPException(status_code=400, detail=f"Target device name '{update_data.new_device}' under process '{update_data.new_process}' already exists")
        
        # Update device registration
        client.command(
            "UPDATE device_register_tb SET process = %(np)s, device = %(nd)s WHERE process = %(op)s AND device = %(od)s",
            parameters={'np': update_data.new_process, 'nd': update_data.new_device, 'op': update_data.old_process, 'od': update_data.old_device}
        )
        return {"message": "Device registration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device registration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/devices", dependencies=[Depends(verify_admin)])
def delete_device(process: str, device: str, client = Depends(get_ch_client)):
    logger.info(f"Deleting device registration: {process}/{device}")
    try:
        # Check if original device exists
        check = client.query(
            "SELECT device FROM device_register_tb WHERE process = %(p)s AND device = %(d)s",
            parameters={'p': process, 'd': device}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Device '{device}' under process '{process}' not found")
        
        # Delete device registration
        client.command(
            "DELETE FROM device_register_tb WHERE process = %(p)s AND device = %(d)s",
            parameters={'p': process, 'd': device}
        )
        return {"message": f"Device '{device}' under process '{process}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------
# Columns Register Table CRUD
# ---------------------------------------------------------------------

@router.get("/columns", response_model=List[ColumnResponse])
def get_columns(client = Depends(get_ch_client)):
    logger.info("Fetching all registered columns")
    try:
        result = client.query("SELECT last_update, process, column_name, column_type, column_key FROM columns_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching columns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/columns", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_column(column_data: ColumnCreate, client = Depends(get_ch_client)):
    logger.info(f"Registering column: {column_data.process}/{column_data.column_name} ({column_data.column_type}, key={column_data.column_key})")
    try:
        register_columns_in_clickhouse_and_postgres([column_data], client)
        benthos_config = regenerate_benthos_kafka_clickhouse_config(client)
        return {
            "message": f"Column '{column_data.column_name}' registered under process '{column_data.process}'",
            "benthos_config": benthos_config,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering column: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/columns/batch", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_columns_batch(batch_data: ColumnBatchCreate, client = Depends(get_ch_client)):
    logger.info("Registering %s column(s) in batch", len(batch_data.columns))
    try:
        register_columns_in_clickhouse_and_postgres(batch_data.columns, client)
        benthos_config = regenerate_benthos_kafka_clickhouse_config(client)
        return {
            "message": f"{len(batch_data.columns)} column(s) registered successfully",
            "benthos_config": benthos_config,
            "columns": [
                {
                    "process": column.process,
                    "column_name": column.column_name,
                    "column_type": column.column_type,
                    "column_key": column.column_key,
                }
                for column in batch_data.columns
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering columns batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/benthos/kafka-clickhouse/regenerate", dependencies=[Depends(verify_admin)])
def regenerate_kafka_clickhouse_benthos(client = Depends(get_ch_client)):
    logger.info("Manually regenerating Benthos Kafka ClickHouse config")
    try:
        benthos_config = regenerate_benthos_kafka_clickhouse_config(client)
        return {
            "message": "Benthos Kafka ClickHouse config regenerated successfully",
            "benthos_config": benthos_config,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating Benthos Kafka ClickHouse config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/columns", dependencies=[Depends(verify_admin)])
def delete_column(process: str, column_name: str, client = Depends(get_ch_client)):
    logger.info(f"Deleting column registration: {process}/{column_name}")
    try:
        # Check if original column exists
        check = client.query(
            "SELECT column_name FROM columns_register_tb WHERE process = %(p)s AND column_name = %(c)s",
            parameters={'p': process, 'c': column_name}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Column '{column_name}' under process '{process}' not found")
        
        # Delete column registration
        client.command(
            "DELETE FROM columns_register_tb WHERE process = %(p)s AND column_name = %(c)s",
            parameters={'p': process, 'c': column_name}
        )
        return {"message": f"Column '{column_name}' under process '{process}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting column: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------
# Project Register Table CRUD
# ---------------------------------------------------------------------

@router.get("/projects", response_model=List[ProjectResponse])
def get_projects(client = Depends(get_ch_client)):
    logger.info("Fetching all project configuration items")
    try:
        result = client.query("SELECT last_update, items, value FROM project_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_project(project_data: ProjectCreate, client = Depends(get_ch_client)):
    logger.info(f"Creating project config item: {project_data.items}")
    try:
        # Check if item key already exists
        dup_check = client.query("SELECT items FROM project_register_tb WHERE items = %(k)s", parameters={'k': project_data.items})
        if dup_check.result_rows:
            raise HTTPException(status_code=400, detail=f"Configuration item '{project_data.items}' already registered")
        
        # Insert item
        client.insert(
            'project_register_tb',
            [[project_data.items, project_data.value]],
            column_names=['items', 'value']
        )
        return {"message": f"Configuration item '{project_data.items}' created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project config item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/projects/{items_key}", dependencies=[Depends(verify_admin)])
def update_project(items_key: str, update_data: ProjectUpdate, client = Depends(get_ch_client)):
    logger.info(f"Updating project config item: {items_key}")
    try:
        # Check if item exists
        check = client.query("SELECT items FROM project_register_tb WHERE items = %(k)s", parameters={'k': items_key})
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Configuration item '{items_key}' not found")
        
        # Update item
        client.command(
            "UPDATE project_register_tb SET value = %(val)s WHERE items = %(k)s",
            parameters={'val': update_data.value, 'k': items_key}
        )
        return {"message": f"Configuration item '{items_key}' updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project config item: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{items_key}", dependencies=[Depends(verify_admin)])
def delete_project(items_key: str, client = Depends(get_ch_client)):
    logger.info(f"Deleting project config item: {items_key}")
    try:
        # Check if item exists
        check = client.query("SELECT items FROM project_register_tb WHERE items = %(k)s", parameters={'k': items_key})
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Configuration item '{items_key}' not found")
        
        # Delete item
        client.command("DELETE FROM project_register_tb WHERE items = %(k)s", parameters={'k': items_key})
        return {"message": f"Configuration item '{items_key}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project config item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------
# Status Register Table CRUD
# ---------------------------------------------------------------------

@router.get("/statuses", response_model=List[StatusRegisterResponse])
def get_statuses(client = Depends(get_ch_client)):
    logger.info("Fetching all registered status colors")
    try:
        result = client.query("SELECT last_update, process, status, color FROM status_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/statuses", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_status(status_data: StatusRegisterCreate, client = Depends(get_ch_client)):
    logger.info(f"Registering status color: {status_data.process}/{status_data.status} ({status_data.color})")
    try:
        # Check for duplicate
        dup_check = client.query(
            "SELECT status FROM status_register_tb WHERE process = %(p)s AND status = %(s)s",
            parameters={'p': status_data.process, 's': status_data.status}
        )
        if dup_check.result_rows:
            raise HTTPException(status_code=400, detail=f"Status '{status_data.status}' under process '{status_data.process}' is already registered")
        
        # Insert status
        client.insert(
            'status_register_tb',
            [[status_data.process, status_data.status, status_data.color]],
            column_names=['process', 'status', 'color']
        )
        return {"message": f"Status '{status_data.status}' registered under process '{status_data.process}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/statuses", dependencies=[Depends(verify_admin)])
def update_status(update_data: StatusRegisterUpdate, client = Depends(get_ch_client)):
    logger.info(f"Updating status registration: {update_data.old_process}/{update_data.old_status} -> {update_data.new_process}/{update_data.new_status}")
    try:
        # Check if original status exists
        check = client.query(
            "SELECT status FROM status_register_tb WHERE process = %(op)s AND status = %(os)s",
            parameters={'op': update_data.old_process, 'os': update_data.old_status}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Status '{update_data.old_status}' under process '{update_data.old_process}' not found")
        
        # Check if new process/status collisions exist
        if (update_data.old_process != update_data.new_process) or (update_data.old_status != update_data.new_status):
            dup_check = client.query(
                "SELECT status FROM status_register_tb WHERE process = %(np)s AND status = %(ns)s",
                parameters={'np': update_data.new_process, 'ns': update_data.new_status}
            )
            if dup_check.result_rows:
                raise HTTPException(status_code=400, detail=f"Target status name '{update_data.new_status}' under process '{update_data.new_process}' already exists")
        
        # Update status registration
        client.command(
            "UPDATE status_register_tb SET process = %(np)s, status = %(ns)s, color = %(color)s WHERE process = %(op)s AND status = %(os)s",
            parameters={
                'np': update_data.new_process,
                'ns': update_data.new_status,
                'color': update_data.new_color,
                'op': update_data.old_process,
                'os': update_data.old_status
            }
        )
        return {"message": "Status registration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status registration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/statuses", dependencies=[Depends(verify_admin)])
def delete_status(process: str, status_name: str = Query(..., alias="status"), client = Depends(get_ch_client)):
    logger.info(f"Deleting status registration: {process}/{status_name}")
    try:
        # Check if exists
        check = client.query(
            "SELECT status FROM status_register_tb WHERE process = %(p)s AND status = %(s)s",
            parameters={'p': process, 's': status_name}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Status '{status_name}' under process '{process}' not found")
        
        # Delete registration
        client.command(
            "DELETE FROM status_register_tb WHERE process = %(p)s AND status = %(s)s",
            parameters={'p': process, 's': status_name}
        )
        return {"message": f"Status '{status_name}' under process '{process}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------
# Alarm Register Table CRUD
# ---------------------------------------------------------------------

@router.get("/alarms", response_model=List[AlarmRegisterResponse])
def get_alarms(client = Depends(get_ch_client)):
    logger.info("Fetching all registered alarm configurations")
    try:
        result = client.query("SELECT last_update, process, status, color FROM alarm_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching alarms: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alarms", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_alarm(alarm_data: AlarmRegisterCreate, client = Depends(get_ch_client)):
    logger.info(f"Registering alarm configuration: {alarm_data.process}/{alarm_data.status} ({alarm_data.color})")
    try:
        # Check for duplicate
        dup_check = client.query(
            "SELECT status FROM alarm_register_tb WHERE process = %(p)s AND status = %(s)s",
            parameters={'p': alarm_data.process, 's': alarm_data.status}
        )
        if dup_check.result_rows:
            raise HTTPException(status_code=400, detail=f"Alarm '{alarm_data.status}' under process '{alarm_data.process}' is already registered")
        
        # Insert alarm
        client.insert(
            'alarm_register_tb',
            [[alarm_data.process, alarm_data.status, alarm_data.color]],
            column_names=['process', 'status', 'color']
        )
        return {"message": f"Alarm '{alarm_data.status}' registered under process '{alarm_data.process}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering alarm: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/alarms", dependencies=[Depends(verify_admin)])
def update_alarm(update_data: AlarmRegisterUpdate, client = Depends(get_ch_client)):
    logger.info(f"Updating alarm registration: {update_data.old_process}/{update_data.old_status} -> {update_data.new_process}/{update_data.new_status}")
    try:
        # Check if original alarm exists
        check = client.query(
            "SELECT status FROM alarm_register_tb WHERE process = %(op)s AND status = %(os)s",
            parameters={'op': update_data.old_process, 'os': update_data.old_status}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Alarm '{update_data.old_status}' under process '{update_data.old_process}' not found")
        
        # Check if new process/status collisions exist
        if (update_data.old_process != update_data.new_process) or (update_data.old_status != update_data.new_status):
            dup_check = client.query(
                "SELECT status FROM alarm_register_tb WHERE process = %(np)s AND status = %(ns)s",
                parameters={'np': update_data.new_process, 'ns': update_data.new_status}
            )
            if dup_check.result_rows:
                raise HTTPException(status_code=400, detail=f"Target alarm name '{update_data.new_status}' under process '{update_data.new_process}' already exists")
        
        # Update alarm registration
        client.command(
            "UPDATE alarm_register_tb SET process = %(np)s, status = %(ns)s, color = %(color)s WHERE process = %(op)s AND status = %(os)s",
            parameters={
                'np': update_data.new_process,
                'ns': update_data.new_status,
                'color': update_data.new_color,
                'op': update_data.old_process,
                'os': update_data.old_status
            }
        )
        return {"message": "Alarm registration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alarm registration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/alarms", dependencies=[Depends(verify_admin)])
def delete_alarm(process: str, status_name: str = Query(..., alias="status"), client = Depends(get_ch_client)):
    logger.info(f"Deleting alarm registration: {process}/{status_name}")
    try:
        # Check if exists
        check = client.query(
            "SELECT status FROM alarm_register_tb WHERE process = %(p)s AND status = %(s)s",
            parameters={'p': process, 's': status_name}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Alarm '{status_name}' under process '{process}' not found")
        
        # Delete registration
        client.command(
            "DELETE FROM alarm_register_tb WHERE process = %(p)s AND status = %(s)s",
            parameters={'p': process, 's': status_name}
        )
        return {"message": f"Alarm '{status_name}' under process '{process}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alarm: {e}")
        raise HTTPException(status_code=500, detail=str(e))

