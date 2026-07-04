import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Header, Query
from database import get_ch_client, format_result
from models import (
    UserCreate, UserUpdate, UserResponse,
    DeviceCreate, DeviceUpdate, DeviceResponse,
    ColumnCreate, ColumnUpdate, ColumnResponse
)

logger = logging.getLogger("DashboardBackend.RegisterRouter")

router = APIRouter(
    prefix="/api",
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
def get_users():
    logger.info("Fetching all users")
    client = get_ch_client()
    try:
        result = client.query("SELECT last_update, user, role FROM user_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_user(user_data: UserCreate):
    logger.info(f"Creating user: {user_data.user}")
    client = get_ch_client()
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
def update_user(username: str, update_data: UserUpdate):
    logger.info(f"Updating user: {username}")
    client = get_ch_client()
    try:
        # Check if user exists
        check = client.query("SELECT user FROM user_register_tb WHERE user = %(u)s", parameters={'u': username})
        if not check.result_rows:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
        
        # Update user
        client.command(
            "ALTER TABLE user_register_tb UPDATE password = %(pwd)s, role = %(role)s, last_update = now() WHERE user = %(u)s",
            parameters={'pwd': update_data.password, 'role': update_data.role, 'u': username}
        )
        return {"message": f"User '{username}' updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{username}", dependencies=[Depends(verify_admin)])
def delete_user(username: str):
    logger.info(f"Deleting user: {username}")
    client = get_ch_client()
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
def get_devices():
    logger.info("Fetching all devices")
    client = get_ch_client()
    try:
        result = client.query("SELECT last_update, process, device FROM device_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/devices", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_device(device_data: DeviceCreate):
    logger.info(f"Registering device: {device_data.process}/{device_data.device}")
    client = get_ch_client()
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
def update_device(update_data: DeviceUpdate):
    logger.info(f"Updating device registration: {update_data.old_process}/{update_data.old_device} -> {update_data.new_process}/{update_data.new_device}")
    client = get_ch_client()
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
            "ALTER TABLE device_register_tb UPDATE process = %(np)s, device = %(nd)s, last_update = now() WHERE process = %(op)s AND device = %(od)s",
            parameters={'np': update_data.new_process, 'nd': update_data.new_device, 'op': update_data.old_process, 'od': update_data.old_device}
        )
        return {"message": "Device registration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device registration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/devices", dependencies=[Depends(verify_admin)])
def delete_device(process: str, device: str):
    logger.info(f"Deleting device registration: {process}/{device}")
    client = get_ch_client()
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
def get_columns():
    logger.info("Fetching all registered columns")
    client = get_ch_client()
    try:
        result = client.query("SELECT last_update, process, column_name, column_type FROM columns_register_tb ORDER BY last_update DESC")
        return format_result(result)
    except Exception as e:
        logger.error(f"Error fetching columns: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/columns", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
def create_column(column_data: ColumnCreate):
    logger.info(f"Registering column: {column_data.process}/{column_data.column_name} ({column_data.column_type})")
    client = get_ch_client()
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
            [[column_data.process, column_data.column_name, column_data.column_type]],
            column_names=['process', 'column_name', 'column_type']
        )
        return {"message": f"Column '{column_data.column_name}' registered under process '{column_data.process}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering column: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/columns", dependencies=[Depends(verify_admin)])
def update_column(update_data: ColumnUpdate):
    logger.info(f"Updating column registration: {update_data.old_process}/{update_data.old_column_name} -> {update_data.new_process}/{update_data.new_column_name}")
    client = get_ch_client()
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
            "ALTER TABLE columns_register_tb UPDATE process = %(np)s, column_name = %(nc)s, column_type = %(nt)s, last_update = now() WHERE process = %(op)s AND column_name = %(oc)s",
            parameters={
                'np': update_data.new_process,
                'nc': update_data.new_column_name,
                'nt': update_data.new_column_type,
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
def delete_column(process: str, column_name: str):
    logger.info(f"Deleting column registration: {process}/{column_name}")
    client = get_ch_client()
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
