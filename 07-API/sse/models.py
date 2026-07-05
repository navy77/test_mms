from pydantic import BaseModel

class RealtimeMessage(BaseModel):
    topic: str
    div: str
    process: str
    device: str
    payload: str
    timestamp: str
