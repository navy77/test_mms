import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Header, Query
from database import get_ch_client, format_result
from models import (
    UserCreate, UserUpdate, UserResponse,
    DeviceCreate, DeviceUpdate, DeviceResponse,
    ColumnCreate, ColumnUpdate, ColumnResponse,
    ProjectCreate, ProjectUpdate, ProjectResponse,
    StatusRegisterCreate, StatusRegisterUpdate, StatusRegisterResponse,
    AlarmRegisterCreate, AlarmRegisterUpdate, AlarmRegisterResponse
)

logger = logging.getLogger("DashboardBackend.RegisterRouter")

router = APIRouter(
    prefix="/api/v1",
    tags=["register"]
)

# Permission Dependency to restrict write operations to admin role
def verify_admin(
    x_role: Optional[str] = Header(None, alias="X-Role"),
    role: Optional[str] = Query(None)
):
    user_role = x_role or role
    if not user_role or user_role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Admin role required."
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
        result = client.query("SELECT last_update, user, role FROM user_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_user(user_data: UserCreate, client = Depends(get_ch_client)):
    logger.info(f"Creating user: {user_data.user}")
    try:
        # Check if user already exists
        dup_check = client.query("SELECT user FROM user_register_tb WHERE user = %(u)s", parameters={'u': user_data.user})
        if dup_check.result_rows:
            raise HTTPException(status_code=400, detail=f"User '{user_data.user}' already registered")
        
        # Insert user
        client.insert(
            'user_register_tb',
            [[user_data.user, user_data.password, user_data.role]],
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
        check = client.query("SELECT user FROM user_register_tb WHERE user = %(u)s", parameters={'u': username})
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        
        # Update user
        client.command(
            "ALTER TABLE user_register_tb UPDATE password = %(pwd)s, role = %(role)s WHERE user = %(u)s",
            parameters={'pwd': update_data.password, 'role': update_data.role, 'u': username}
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
        check = client.query("SELECT user FROM user_register_tb WHERE user = %(u)s", parameters={'u': username})
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        
        # Delete user
        client.command("DELETE FROM user_register_tb WHERE user = %(u)s", parameters={'u': username})
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
            "ALTER TABLE device_register_tb UPDATE process = %(np)s, device = %(nd)s WHERE process = %(op)s AND device = %(od)s",
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
        # Check for duplicate
        dup_check = client.query(
            "SELECT column_name FROM columns_register_tb WHERE process = %(p)s AND column_name = %(c)s",
            parameters={'p': column_data.process, 'c': column_data.column_name}
        )
        if dup_check.result_rows:
            raise HTTPException(status_code=400, detail=f"Column '{column_data.column_name}' under process '{column_data.process}' is already registered")
        
        # Insert column
        client.insert(
            'columns_register_tb',
            [[column_data.process, column_data.column_name, column_data.column_type, column_data.column_key]],
            column_names=['process', 'column_name', 'column_type', 'column_key']
        )
        return {"message": f"Column '{column_data.column_name}' registered under process '{column_data.process}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering column: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/columns", dependencies=[Depends(verify_admin)])
def update_column(update_data: ColumnUpdate, client = Depends(get_ch_client)):
    logger.info(f"Updating column registration: {update_data.old_process}/{update_data.old_column_name} -> {update_data.new_process}/{update_data.new_column_name}")
    try:
        # Check if original column exists
        check = client.query(
            "SELECT column_name FROM columns_register_tb WHERE process = %(op)s AND column_name = %(oc)s",
            parameters={'op': update_data.old_process, 'oc': update_data.old_column_name}
        )
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"Column '{update_data.old_column_name}' under process '{update_data.old_process}' not found")
        
        # Check if the new name would collide with another existing entry
        if (update_data.old_process != update_data.new_process) or (update_data.old_column_name != update_data.new_column_name):
            dup_check = client.query(
                "SELECT column_name FROM columns_register_tb WHERE process = %(np)s AND column_name = %(nc)s",
                parameters={'np': update_data.new_process, 'nc': update_data.new_column_name}
            )
            if dup_check.result_rows:
                raise HTTPException(status_code=400, detail=f"Target column name '{update_data.new_column_name}' under process '{update_data.new_process}' already exists")
        
        # Update column registration
        client.command(
            "ALTER TABLE columns_register_tb UPDATE process = %(np)s, column_name = %(nc)s, column_type = %(nt)s, column_key = %(nk)s WHERE process = %(op)s AND column_name = %(oc)s",
            parameters={
                'np': update_data.new_process,
                'nc': update_data.new_column_name,
                'nt': update_data.new_column_type,
                'nk': update_data.new_column_key,
                'op': update_data.old_process,
                'oc': update_data.old_column_name
            }
        )
        return {"message": "Column registration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating column registration: {e}")
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
            "ALTER TABLE project_register_tb UPDATE value = %(val)s WHERE items = %(k)s",
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
            "ALTER TABLE status_register_tb UPDATE process = %(np)s, status = %(ns)s, color = %(color)s WHERE process = %(op)s AND status = %(os)s",
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
            "ALTER TABLE alarm_register_tb UPDATE process = %(np)s, status = %(ns)s, color = %(color)s WHERE process = %(op)s AND status = %(os)s",
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

