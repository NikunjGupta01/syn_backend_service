# app/routes/DeviceMasterRoutes.py
from fastapi import Request, APIRouter
from app.controllers.DeviceMasterController import (
    DeviceMasterRequest,
    ChangeDeviceStatusRequest,
)

router = APIRouter()


async def list_devices_handler(request: Request):
    from app.controllers.DeviceMasterController import DeviceMasterController

    return await DeviceMasterController().list_devices(request)


async def device_by_topic_handler(topic: str, request: Request):
    from app.controllers.DeviceMasterController import DeviceMasterController

    return await DeviceMasterController().device_by_topic(topic, request)


@router.post(path="/add")
async def add_device(payload: DeviceMasterRequest):
    from app.controllers.DeviceMasterController import DeviceMasterController

    return await DeviceMasterController().add_device(payload)


@router.post(path="/resync")
async def resync_device_status(payload: ChangeDeviceStatusRequest):
    from app.controllers.DeviceMasterController import DeviceMasterController

    return await DeviceMasterController().resync_device_status(payload)
