from pydantic import BaseModel
from typing import List, Any

class HistoryResponse(BaseModel):
    device: str
    data: List[Any]
