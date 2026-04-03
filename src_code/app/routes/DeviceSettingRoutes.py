from fastapi import Request, APIRouter
from app.controllers.DeviceSettingsController import (
    DeviceSettingsController,
    DeviceSettingUpdateRequest,
)


router = APIRouter()


@router.get("/get")
async def get_setting(topic: str):
    return await DeviceSettingsController().get_one(topic=topic)


@router.put("/update-core")
async def update_setting(payload: DeviceSettingUpdateRequest):
    return await DeviceSettingsController().update_core_settings(payload=payload)
