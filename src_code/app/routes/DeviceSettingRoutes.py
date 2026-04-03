from fastapi import Request, APIRouter
from app.controllers.DeviceSettingsController import (
    DeviceSettingsController,
    DeviceSettingUpdateRequest,
    AirplaneModeRequest,
    LedStatusRequest,
)


router = APIRouter()


@router.get("/get")
async def get_setting(topic: str):
    return await DeviceSettingsController().get_one(topic=topic)


@router.put("/update-core")
async def update_setting(payload: DeviceSettingUpdateRequest):
    return await DeviceSettingsController().update_core_settings(payload=payload)


@router.post("/airplane-mode")
async def set_airplane_mode(payload: AirplaneModeRequest):
    return await DeviceSettingsController().set_airplane_mode(payload=payload)


@router.post("/led-status")
async def set_led_status(payload: LedStatusRequest):
    return await DeviceSettingsController().set_led_status(payload=payload)
