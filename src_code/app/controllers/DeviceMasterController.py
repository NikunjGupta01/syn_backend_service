# app/controllers/DeviceMasterController.py
from fastapi import Request
from fastapi.responses import JSONResponse
from app.models import get_db
from datetime import datetime
from app.config.config import settings
from pydantic import BaseModel
from app.models.DeviceMaster import DeviceMaster
from app.controllers.APIResponse import APIResponse
from app.helpers.ErrorCodes import ErrorCodes
from typing import Optional
import httpx


class DeviceMasterRequest(BaseModel):
    topic: str
    imei: Optional[str] = None
    interval: Optional[int] = None
    Geoid: Optional[str] = None
    created_at: Optional[datetime] = None
    student_name: Optional[str] = None
    student_id: Optional[str] = None
    is_active: Optional[bool] = False


class ChangeDeviceStatusRequest(BaseModel):
    topic: str
    is_active: bool


def serialize_device(record):
    if not record:
        return None

    data = record.dict()

    created = data.get("created_at")

    # Normalize datetime → string
    if isinstance(created, datetime):
        created_stripped = created.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(created, str):
        created_stripped = created.split(".")[0]
    else:
        created_stripped = None

    return {
        "topic": data.get("topic"),
        "imei": data.get("imei"),
        "interval": data.get("interval"),
        "geoid": data.get("Geoid"),  # USE EXACT DB FIELD
        "student_name": data.get("student_name"),
        "student_id": data.get("student_id"),
        "is_active": data.get("is_active"),
        "is_subscribed": data.get("is_subscribed"),
        "createdAt": created_stripped,
    }


class DeviceMasterController:

    async def list_devices(self, request: Request):
        try:
            db = get_db()
            records = await db.find(DeviceMaster, {})

            devices = [serialize_device(r) for r in records]

            return JSONResponse(
                APIResponse.success(
                    msg="Device list fetched successfully", data=devices
                ),
                status_code=ErrorCodes.SUCCESS,
            )

        except Exception as e:
            return JSONResponse(
                APIResponse.error(
                    msg=f"Unexpected error: {str(e)}",
                    code=ErrorCodes.INTERNAL_SERVER_ERROR,
                ),
                status_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            )

    async def device_by_topic(self, topic: str, request: Request):
        try:
            db = get_db()
            record = await db.find_one(DeviceMaster, {"topic": topic})

            if not record:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device not found", code=ErrorCodes.NOT_FOUND
                    ),
                    status_code=ErrorCodes.NOT_FOUND,
                )

            return JSONResponse(
                APIResponse.success(
                    msg="Device fetched successfully", data=serialize_device(record)
                ),
                status_code=ErrorCodes.SUCCESS,
            )

        except Exception as e:
            return JSONResponse(
                APIResponse.error(
                    msg=f"Unexpected error: {str(e)}",
                    code=ErrorCodes.INTERNAL_SERVER_ERROR,
                ),
                status_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            )

    async def add_device(self, payload: DeviceMasterRequest):
        try:
            db = get_db()

            # Check if device already exists
            record = await db.find_one(DeviceMaster, {"topic": payload.topic})
            if record:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device Already Exists", code=ErrorCodes.BAD_REQUEST
                    ),
                    status_code=ErrorCodes.BAD_REQUEST,
                )

            # Create new device
            device = DeviceMaster(
                topic=payload.topic,
                imei=payload.imei,
                interval=payload.interval,
                Geoid=payload.Geoid,
                student_name=payload.student_name,
                student_id=payload.student_id,
                is_active=payload.is_active,
                created_at=datetime.utcnow(),  # 👈 good practice
            )

            new_record = await db.save(device)

            return JSONResponse(
                APIResponse.success(
                    msg="Device added successfully", data=serialize_device(new_record)
                ),
                status_code=ErrorCodes.SUCCESS,
            )

        except Exception as e:
            return JSONResponse(
                APIResponse.error(
                    msg=f"Unexpected error: {str(e)}",
                    code=ErrorCodes.INTERNAL_SERVER_ERROR,
                ),
                status_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            )

    async def resync_device_status(self, payload: ChangeDeviceStatusRequest):

        try:
            db = get_db()

            # Check if device already exists
            record = await db.find_one(DeviceMaster, {"topic": payload.topic})
            if record is None:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device Does Not Exist", code=ErrorCodes.BAD_REQUEST
                    ),
                    status_code=ErrorCodes.BAD_REQUEST,
                )
            sync_dict = {"topic": payload.topic, "is_active": payload.is_active}
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(
                    f"{settings.WORKER_APP_URL}/resync-topic",
                    params={"topic": payload.topic, "is_active": payload.is_active},
                )

            if res.status_code == 200:
                record.is_active = payload.is_active
                updated_record = await db.save(record)

                return JSONResponse(
                    APIResponse.success(
                        msg=(
                            "Device activated"
                            if payload.is_active
                            else "Device Deactivated"
                        ),
                        data=serialize_device(updated_record),
                    ),
                    status_code=ErrorCodes.SUCCESS,
                )
            else:
                return JSONResponse(
                    APIResponse.error(
                        msg=("Device subscription failed. Please try again later"),
                        data=serialize_device(updated_record),
                    ),
                    status_code=ErrorCodes.SUCCESS,
                )

        except Exception as e:
            return JSONResponse(
                APIResponse.error(
                    msg=f"Unexpected error: {str(e)}",
                    code=ErrorCodes.INTERNAL_SERVER_ERROR,
                ),
                status_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            )
