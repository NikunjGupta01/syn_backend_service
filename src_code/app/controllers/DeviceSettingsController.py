from datetime import datetime
from typing import Optional
import json
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.libraries.MqttConnector import mqtt_connector
from app.controllers.APIResponse import APIResponse
from app.helpers.ErrorCodes import ErrorCodes
from app.models import get_db
from app.models.DeviceMaster import DeviceMaster
from app.models.DeviceSetting import DeviceSetting
import asyncio


class DeviceSettingUpdateRequest(BaseModel):
    topic: str
    normal_sending_interval: Optional[int] = Field(None, alias="NormalSendingInterval")
    sos_sending_interval: Optional[int] = Field(None, alias="SOSSendingInterval")
    normal_scanning_interval: Optional[int] = Field(
        None, alias="NormalScanningInterval"
    )
    airplane_interval: Optional[int] = Field(None, alias="AirplaneInterval")
    temperature_limit: Optional[int] = Field(None, alias="TemperatureLimit")
    speed_limit: Optional[int] = Field(None, alias="SpeedLimit")
    lowbat_limit: Optional[int] = Field(None, alias="LowbatLimit")
    phone_num1: Optional[str] = Field(None, alias="phonenum1")
    phone_num2: Optional[str] = Field(None, alias="phonenum2")
    control_room_num: Optional[str] = Field(None, alias="controlroomnum")
    current_profile: Optional[str] = Field(None, alias="currentprofile")

    model_config = {"populate_by_name": True}


client = mqtt_connector.client


def request_device_settings_query(imei: str):
    if not client.is_connected():
        return False, "MQTT client not connected"

    command_topic = f"{imei}/sub"
    result = client.publish(command_topic, json.dumps({"Query": "DeviceSettings"}))
    if result.rc != 0:
        return False, f"MQTT publish failed rc={result.rc}"

    return True, "DeviceSettings query published"


def update_device_settings_command(imei: str, settings: dict):
    """
    Publish a settings update to the device topic.
    Expected keys (strings): NormalSendingInterval, SOSSendingInterval, NormalScanningInterval,
    AirplaneInterval, TemperatureLimit, SpeedLimit.
    """
    if not client.is_connected():
        return False, "MQTT client not connected"

    command_topic = f"{imei}/sub"
    payload = json.dumps(settings)
    result = client.publish(command_topic, payload)
    if result.rc != 0:
        return False, f"MQTT publish failed rc={result.rc}"

    return True, "Device settings update published"


def serialize_device_setting(record: DeviceSetting):
    return {
        "topic": getattr(record.device, "topic", None),
        "imei": getattr(record.device, "imei", None),
        "normal_sending_interval": record.normal_sending_interval,
        "sos_sending_interval": record.sos_sending_interval,
        "normal_scanning_interval": record.normal_scanning_interval,
        "airplane_interval": record.airplane_interval,
        "temperature_limit": record.temperature_limit,
        "speed_limit": record.speed_limit,
        "lowbat_limit": record.lowbat_limit,
        "phone_num1": record.phone_num1,
        "phone_num2": record.phone_num2,
        "control_room_num": record.control_room_num,
        "current_profile": record.current_profile,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


ALLOWED_COMMAND_FIELDS = {
    "NormalSendingInterval",
    "SOSSendingInterval",
    "NormalScanningInterval",
    "AirplaneInterval",
    "SpeedLimit",
    "LowbatLimit",
    "TemperatureLimit",
}
COMMAND_TO_ATTR = {
    "NormalSendingInterval": "normal_sending_interval",
    "SOSSendingInterval": "sos_sending_interval",
    "NormalScanningInterval": "normal_scanning_interval",
    "AirplaneInterval": "airplane_interval",
    "SpeedLimit": "speed_limit",
    "LowbatLimit": "lowbat_limit",
    "TemperatureLimit": "temperature_limit",
}


class DeviceSettingsController:
    async def get_one(self, topic: str):

        try:
            db = get_db()

            device = await db.find_one(DeviceMaster, {"topic": topic})

            if not device:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device not found",
                        code=ErrorCodes.NOT_FOUND,
                    ),
                    status_code=ErrorCodes.NOT_FOUND,
                )
            settings_record = await db.find_one(
                DeviceSetting, DeviceSetting.device == device.id
            )
            if not settings_record:
                ok, publish_message = request_device_settings_query(device.imei)
                if not ok:
                    return JSONResponse(
                        APIResponse.error(
                            msg=f"Device settings request failed: {publish_message}",
                            code=ErrorCodes.INTERNAL_SERVER_ERROR,
                        )
                    )
                timeout_seconds = 30
                poll_interval = 5
                attempts = int(timeout_seconds / poll_interval)

                for _ in range(attempts):
                    settings_record = await db.find_one(
                        DeviceSetting, DeviceSetting.device == device.id
                    )
                    if settings_record:
                        return JSONResponse(
                            APIResponse.success(
                                msg="Device settings fetched successfully",
                                data=serialize_device_setting(settings_record),
                            ),
                            status_code=ErrorCodes.SUCCESS,
                        )
                    await asyncio.sleep(poll_interval)

                # timeout fallback
                return JSONResponse(
                    APIResponse.success(
                        msg="Device settings request sent. Response not received yet.",
                        data={"topic": topic, "status": "pending"},
                        code=ErrorCodes.ACCEPTED,
                    ),
                    status_code=ErrorCodes.ACCEPTED,
                )

            return JSONResponse(
                APIResponse.success(
                    msg="Device settings fetched successfully",
                    data=serialize_device_setting(settings_record),
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

    async def update_core_settings(self, payload: DeviceSettingUpdateRequest):
        try:
            db = get_db()

            device = await db.find_one(DeviceMaster, {"topic": payload.topic})
            if not device:
                return JSONResponse(
                    APIResponse.error(
                        msg="Device not found",
                        code=ErrorCodes.NOT_FOUND,
                    ),
                    status_code=ErrorCodes.NOT_FOUND,
                )

            updates_raw = payload.model_dump(by_alias=True, exclude_unset=True)
            updates_raw.pop("topic", None)

            # only allow core settings fields that the command supports
            updates = {
                k: v for k, v in updates_raw.items() if k in ALLOWED_COMMAND_FIELDS
            }

            if not updates:
                return JSONResponse(
                    APIResponse.error(
                        msg="No updatable settings provided",
                        code=ErrorCodes.BAD_REQUEST,
                    ),
                    status_code=ErrorCodes.BAD_REQUEST,
                )

            ok, publish_message = update_device_settings_command(device.imei, updates)
            if not ok:
                return JSONResponse(
                    APIResponse.error(
                        msg=f"Device settings update failed: {publish_message}",
                        code=ErrorCodes.INTERNAL_SERVER_ERROR,
                    ),
                    status_code=ErrorCodes.INTERNAL_SERVER_ERROR,
                )

            # Give device a moment, then request fresh settings
            await asyncio.sleep(2)
            request_device_settings_query(device.imei)

            # Poll for updated settings saved by worker after device responds
            timeout_seconds = 15
            poll_interval = 5
            attempts = int(timeout_seconds / poll_interval)
            last_settings_record = None

            for _ in range(attempts):
                settings_record = await db.find_one(
                    DeviceSetting, DeviceSetting.device == device.id
                )
                if settings_record:
                    last_settings_record = settings_record
                    all_match = True
                    for cmd_field, desired in updates.items():
                        attr_name = COMMAND_TO_ATTR.get(cmd_field)
                        if not attr_name:
                            continue
                        current_val = getattr(settings_record, attr_name, None)
                        if str(desired) != str(current_val):
                            all_match = False
                            break
                    if all_match:
                        return JSONResponse(
                            APIResponse.success(
                                msg="Device Settings Updated Successfully",
                                data=serialize_device_setting(settings_record),
                            ),
                            status_code=ErrorCodes.SUCCESS,
                        )
                await asyncio.sleep(poll_interval)

            return JSONResponse(
                APIResponse.success(
                    msg=(
                        "Device responded but values differ from requested"
                        if last_settings_record
                        else "Device settings command sent. Awaiting device response."
                    ),
                    data=(
                        serialize_device_setting(last_settings_record)
                        if last_settings_record
                        else {"topic": payload.topic, "status": "pending"}
                    ),
                    code=ErrorCodes.ACCEPTED,
                ),
                status_code=ErrorCodes.ACCEPTED,
            )

        except Exception as e:
            return JSONResponse(
                APIResponse.error(
                    msg=f"Unexpected error: {str(e)}",
                    code=ErrorCodes.INTERNAL_SERVER_ERROR,
                ),
                status_code=ErrorCodes.INTERNAL_SERVER_ERROR,
            )
