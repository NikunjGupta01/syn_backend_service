# app/models/DeviceCommand.py

from odmantic import Field, Model
from datetime import datetime
from typing import Dict, Any, Optional


class DeviceCommand(Model):
    imei: str
    command: str
    payload: Dict[str, Any]
    qos: int
    status: str  # SENT | DELIVERED | FAILED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = {"collection": "device_commands"}
