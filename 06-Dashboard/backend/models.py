from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# =====================================================================
# Pydantic Schemas
# =====================================================================

# User schemas
class UserCreate(BaseModel):
    user: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")
    role: str = Field("user", description="User role (e.g. admin, user)")

class UserUpdate(BaseModel):
    password: str = Field(..., min_length=1, description="New password")
    role: str = Field(..., min_length=1, description="New role")

class UserResponse(BaseModel):
    last_update: Optional[datetime] = None
    user: str
    role: str

# Device schemas
class DeviceCreate(BaseModel):
    process: str = Field(..., min_length=1, description="Process name")
    device: str = Field(..., min_length=1, description="Device name")

class DeviceUpdate(BaseModel):
    old_process: str = Field(..., min_length=1, description="Current process name")
    old_device: str = Field(..., min_length=1, description="Current device name")
    new_process: str = Field(..., min_length=1, description="New process name")
    new_device: str = Field(..., min_length=1, description="New device name")

class DeviceResponse(BaseModel):
    last_update: Optional[datetime] = None
    process: str
    device: str

# Column schemas
class ColumnCreate(BaseModel):
    process: str = Field(..., min_length=1, description="Process name")
    column_name: str = Field(..., min_length=1, description="Column name")
    column_type: str = Field(..., min_length=1, description="Column data type (e.g. String, Float32)")

class ColumnUpdate(BaseModel):
    old_process: str = Field(..., min_length=1, description="Current process name")
    old_column_name: str = Field(..., min_length=1, description="Current column name")
    new_process: str = Field(..., min_length=1, description="New process name")
    new_column_name: str = Field(..., min_length=1, description="New column name")
    new_column_type: str = Field(..., min_length=1, description="New column data type")

class ColumnResponse(BaseModel):
    last_update: Optional[datetime] = None
    process: str
    column_name: str
    column_type: str
