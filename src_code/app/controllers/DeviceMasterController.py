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
    imei: str


class ChangeDeviceStatusRequest(BaseModel):
    topic: str
    is_active: bool


def serialize_device(record):
    if not record:
        return None

    data = record.dict()

    created = data.get("created_at")
    updated = data.get("updated_at")

    # Normalize datetime → string
    if isinstance(created, datetime):
        created_stripped = created.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(created, str):
        created_stripped = created.split(".")[0]
    else:
        created_stripped = None

    if isinstance(updated, datetime):
        updated_stripped = updated.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(updated, str):
        updated_stripped = updated.split(".")[0]
    else:
        updated_stripped = None

    return {
        "topic": data.get("topic"),
        "imei": data.get("imei"),
        "interval": data.get("interval"),
        "geoid": data.get("Geoid"),  # USE EXACT DB FIELD
        "packet": data.get("packet"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "speed": data.get("speed"),
        "temperature": data.get("temperature"),
        "current_mode": data.get("current_mode"),
        "led_status": data.get("led_status"),
        "timestamp": data.get("timestamp"),
        "battery": data.get("Battery"),
        "signal": data.get("Signal"),
        "gps_strength": data.get("GPSStrength"),
        "student_name": data.get("student_name"),
        "student_id": data.get("student_id"),
        "is_active": data.get("is_active"),
        "is_subscribed": data.get("is_subscribed"),
        "createdAt": created_stripped,
        "updatedAt": updated_stripped,
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
            imei = payload.imei.strip()
            topic = f"{imei}/pub"

            # Check if device already exists
            record = await db.find_one(DeviceMaster, {"topic": topic})
            if record:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device Already Exists", code=ErrorCodes.BAD_REQUEST
                    ),
                    status_code=ErrorCodes.BAD_REQUEST,
                )

            # Create new device
            device = DeviceMaster(
                topic=topic,
                imei=imei,
                is_active=True,
                is_subscribed=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            new_record = await db.save(device)
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(
                    f"{settings.WORKER_APP_URL}/resync-topic",
                    params={"topic": new_record.topic, "is_active": True},
                )

            if res.status_code != ErrorCodes.SUCCESS:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device added but subscription sync failed. Please retry resync.",
                        code=ErrorCodes.SERVICE_UNAVAILABLE,
                    ),
                    status_code=ErrorCodes.SERVICE_UNAVAILABLE,
                )

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
                    ),
                    status_code=ErrorCodes.SERVICE_UNAVAILABLE,
                )

        except Exception as e:
            return JSONResponse(
                APIResponse.error(
                    msg=f"Unexpected error: {str(e)}",
                    code=ErrorCodes.INTERNAL_SERVER_ERROR,
                ),
                status_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            )

    async def delete_device(self, topic: str):
        try:
            db = get_db()
            record = await db.find_one(DeviceMaster, {"topic": topic})

            if record is None:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device Does Not Exist", code=ErrorCodes.NOT_FOUND
                    ),
                    status_code=ErrorCodes.NOT_FOUND,
                )

            await db.delete(record)

            return JSONResponse(
                APIResponse.success(msg="Device deleted successfully"),
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
