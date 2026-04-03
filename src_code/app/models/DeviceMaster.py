# app/models/DeviceMaster.py
from odmantic import Field, Model
from typing import Optional
from datetime import datetime


class DeviceMaster(Model):
    topic: str
    imei: str
    interval: Optional[int] = None
    Geoid: Optional[str] = None
    packet: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    speed: Optional[str] = None
    temperature: Optional[str] = None
    timestamp: Optional[str] = None
    Battery: Optional[str] = None
    Signal: Optional[str] = None
    GPSStrength: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    student_name: Optional[str] = None
    student_id: Optional[str] = None
    is_active: bool = True
    is_subscribed: bool = False

    model_config = {"collection": "devices_master"}
