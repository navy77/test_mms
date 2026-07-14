from datetime import datetime
from typing import List, Optional
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
    column_key: bool = Field(False, description="Is this a key/indexing column (True) or a data column (False)?")

class ColumnBatchCreate(BaseModel):
    columns: List[ColumnCreate] = Field(..., min_length=1, description="Columns to register")

class ColumnResponse(BaseModel):
    last_update: Optional[datetime] = None
    process: str
    column_name: str
    column_type: str
    column_key: bool


# Project Config schemas
class ProjectCreate(BaseModel):
    items: str = Field(..., min_length=1, description="Configuration item key")
    value: str = Field(..., min_length=1, description="Configuration item value")

class ProjectUpdate(BaseModel):
    value: str = Field(..., min_length=1, description="New configuration item value")

class ProjectResponse(BaseModel):
    last_update: Optional[datetime] = None
    items: str
    value: str


# Status Settings schemas
class StatusRegisterCreate(BaseModel):
    process: str = Field(..., min_length=1, description="Process name")
    status: str = Field(..., min_length=1, description="Status name")
    color: str = Field(..., min_length=1, description="Color hex or representation")

class StatusRegisterUpdate(BaseModel):
    old_process: str = Field(..., min_length=1, description="Current process name")
    old_status: str = Field(..., min_length=1, description="Current status name")
    new_process: str = Field(..., min_length=1, description="New process name")
    new_status: str = Field(..., min_length=1, description="New status name")
    new_color: str = Field(..., min_length=1, description="New color")

class StatusRegisterResponse(BaseModel):
    last_update: Optional[datetime] = None
    process: str
    status: str
    color: str


# Alarm Settings schemas
class AlarmRegisterCreate(BaseModel):
    process: str = Field(..., min_length=1, description="Process name")
    status: str = Field(..., min_length=1, description="Status/Alarm name")
    color: str = Field(..., min_length=1, description="Color hex or representation")

class AlarmRegisterUpdate(BaseModel):
    old_process: str = Field(..., min_length=1, description="Current process name")
    old_status: str = Field(..., min_length=1, description="Current status/alarm name")
    new_process: str = Field(..., min_length=1, description="New process name")
    new_status: str = Field(..., min_length=1, description="New status/alarm name")
    new_color: str = Field(..., min_length=1, description="New color")

class AlarmRegisterResponse(BaseModel):
    last_update: Optional[datetime] = None
    process: str
    status: str
    color: str


class DeviceStatusCountResponse(BaseModel):
    process: str
    online: int
    offline: int
    communication_fail: int
    total: int


