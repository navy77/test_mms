from pydantic import BaseModel
from typing import List, Any

class DataResponse(BaseModel):
    device: str
    data: List[Any]

class DailyDataResponse(BaseModel):
    date: str
    device: str
    data: List[Any]

class MonthlyDataResponse(BaseModel):
    month: str
    device: str
    data: List[Any]

class StatusSegment(BaseModel):
    status: str
    duration: float
    ratio: float

class StatusResponse(BaseModel):
    device: str
    data: List[StatusSegment]
    utilize: float

class DailyStatusResponse(BaseModel):
    date: str
    device: str
    data: List[StatusSegment]
    utilize: float

class MonthlyStatusResponse(BaseModel):
    month: str
    device: str
    data: List[StatusSegment]
    utilize: float

class AlarmSegment(BaseModel):
    alarm: str
    duration: float
    ratio: float

class AlarmResponse(BaseModel):
    device: str
    data: List[AlarmSegment]

class DailyAlarmResponse(BaseModel):
    date: str
    device: str
    data: List[AlarmSegment]

class MonthlyAlarmResponse(BaseModel):
    month: str
    device: str
    data: List[AlarmSegment]


class DeviceSegment(BaseModel):
    status: str
    duration: float
    ratio: float

class DeviceResponse(BaseModel):
    device: str
    data: List[DeviceSegment]

class DailyDeviceResponse(BaseModel):
    date: str
    device: str
    data: List[DeviceSegment]

class MonthlyDeviceResponse(BaseModel):
    month: str
    device: str
    data: List[DeviceSegment]


class DeviceStatusCountResponse(BaseModel):
    process: str
    online: int
    offline: int
    communication_fail: int
    total: int


class TimelineSegment(BaseModel):
    status: str
    start_time: str
    end_time: str
    duration: float


class TimelineResponse(BaseModel):
    device: str
    data: List[TimelineSegment]


