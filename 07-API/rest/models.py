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

class DailyStatusResponse(BaseModel):
    date: str
    device: str
    data: List[StatusSegment]

class MonthlyStatusResponse(BaseModel):
    month: str
    device: str
    data: List[StatusSegment]
