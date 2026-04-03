# app/models/DeviceSetting.py
from odmantic import Model, Reference, Index, Field
from typing import Optional
from datetime import datetime

from app.models.DeviceMaster import DeviceMaster


class DeviceSetting(Model):
    device: DeviceMaster = Reference()
    normal_sending_interval: Optional[int] = Field(
        None, key_name="NormalSendingInterval"
    )
    sos_sending_interval: Optional[int] = Field(None, key_name="SOSSendingInterval")
    normal_scanning_interval: Optional[int] = Field(
        None, key_name="NormalScanningInterval"
    )
    airplane_interval: Optional[int] = Field(None, key_name="AirplaneInterval")
    temperature_limit: Optional[int] = Field(None, key_name="TemperatureLimit")
    speed_limit: Optional[int] = Field(None, key_name="SpeedLimit")
    lowbat_limit: Optional[int] = Field(None, key_name="LowbatLimit")
    phone_num1: Optional[str] = Field(None, key_name="phonenum1")
    phone_num2: Optional[str] = Field(None, key_name="phonenum2")
    control_room_num: Optional[str] = Field(None, key_name="controlroomnum")
    current_profile: Optional[str] = Field(None, key_name="currentprofile")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "device_settings",
        "indexes": lambda: [Index(DeviceSetting.device, unique=True)],
    }
