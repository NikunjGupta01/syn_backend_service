# app/graphql/DeviceMasterGraphQLSchema.py
import json
import strawberry
from datetime import datetime
from strawberry.exceptions import GraphQLError
from fastapi import Request


def convert_device(record: dict):
    if not record:
        return {}

    created = record.get("createdAt")
    if isinstance(created, datetime):
        created_stripped = created.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(created, str):
        created_stripped = created.split(".")[0]
    else:
        created_stripped = None

    updated = record.get("updatedAt")
    if isinstance(updated, datetime):
        updated_stripped = updated.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(updated, str):
        updated_stripped = updated.split(".")[0]
    else:
        updated_stripped = None

    return {
        "topic": record.get("topic"),
        "imei": record.get("imei"),
        "interval": record.get("interval"),
        "geoid": record.get("geoid"),
        "packet": record.get("packet"),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "speed": record.get("speed"),
        "temperature": record.get("temperature"),
        "timestamp": record.get("timestamp"),
        "battery": record.get("battery"),
        "signal": record.get("signal"),
        "gpsStrength": record.get("gps_strength"),
        "isActive": record.get("is_active"),
        "isSubscribed": record.get("is_subscribed"),
        "createdAt": created_stripped,
        "updatedAt": updated_stripped,
        "studentName": record.get("student_name"),
        "studentId": record.get("student_id"),
    }


@strawberry.type
class DeviceType:
    topic: str
    imei: str | None
    interval: int | None
    geoid: str | None
    packet: str | None
    latitude: str | None
    longitude: str | None
    speed: str | None
    temperature: str | None
    timestamp: str | None
    battery: str | None
    signal: str | None
    gpsStrength: str | None
    isActive: bool | None
    isSubscribed: bool | None
    createdAt: str | None
    updatedAt: str | None
    studentName: str | None
    studentId: str | None


@strawberry.type
class Query:

    @strawberry.field
    async def devices(self, info) -> list[DeviceType]:
        from app.routes.DeviceMasterRoutes import list_devices_handler

        request: Request = info.context["request"]
        response = await list_devices_handler(request)

        if response.status_code != 200:
            raise GraphQLError(response.body.decode())

        data = json.loads(response.body.decode())["data"]
        return [DeviceType(**convert_device(item)) for item in data]

    @strawberry.field
    async def deviceByTopic(self, topic: str, info) -> DeviceType:
        from app.routes.DeviceMasterRoutes import device_by_topic_handler

        request: Request = info.context["request"]
        response = await device_by_topic_handler(topic, request)

        if response.status_code != 200:
            raise GraphQLError(response.body.decode())

        data = json.loads(response.body.decode())["data"]
        return DeviceType(**convert_device(data))


schema = strawberry.Schema(query=Query)
