# app/controllers/CommandController.py

import json
import logging
from app.models import get_db
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from datetime import datetime, timezone
from app.models.GeofenceData import GeofenceData
from app.models.DeviceCommand import DeviceCommand
from app.libraries.MqttConnector import mqtt_connector
from app.constants.CommandDefinitions import COMMAND_DEFINITIONS

IST = ZoneInfo("Asia/Kolkata")


class CommandController:

    @staticmethod
    async def send(command_req):

        if command_req.command not in COMMAND_DEFINITIONS:
            raise HTTPException(400, "Unsupported command")

        definition = COMMAND_DEFINITIONS[command_req.command]

        # STRICT validation for SET_CONTACTS (firmware page 2)
        if command_req.command == "SET_CONTACTS":
            for k in ("phonenum1", "phonenum2", "controlroomnum"):
                v = command_req.params.get(k)
                if not v or not str(v).isdigit():
                    raise HTTPException(400, f"{k} must be numeric")

        # BASIC validation for SET_GEOFENCE (you were missing this)
        if command_req.command == "SET_GEOFENCE":
            required_keys = ("geofence_number", "geofence_id", "coordinates")
            for k in required_keys:
                if k not in command_req.params:
                    raise HTTPException(400, f"{k} is required")

            coordinates = command_req.params["coordinates"]
            if not isinstance(coordinates, list):
                raise HTTPException(400, "coordinates must be a list")

            if len(coordinates) != 5:
                raise HTTPException(400, "coordinates must contain exactly 5 points")

            # Validate each coordinate structure
            for point in coordinates:

                if not isinstance(point, dict):
                    raise HTTPException(400, "each coordinate must be an object")

                if "lat" not in point or "lng" not in point:
                    raise HTTPException(400, "each coordinate must contain lat and lng")

                if not isinstance(point["lat"], (int, float)) or not isinstance(
                    point["lng"], (int, float)
                ):
                    raise HTTPException(400, "lat and lng must be numeric")

        payload = {**definition["payload"], **command_req.params}
        topic = f"{command_req.imei}/sub"
        qos = definition["qos"]

        client = mqtt_connector.client

        if not client.is_connected():
            logger.error("MQTT client not connected (imei=%s)", command_req.imei)
            raise HTTPException(503, "MQTT broker not connected")

        result = mqtt_connector.client.publish(topic, json.dumps(payload), qos=qos)

        if result.rc != 0:
            logger.error(
                "MQTT publish failed rc=%s imei=%s topic=%s",
                result.rc,
                command_req.imei,
                topic,
            )
            raise HTTPException(500, f"MQTT publish failed rc={result.rc}")

        created_at_ist = datetime.now(timezone.utc).astimezone(IST).replace(tzinfo=None)

        db = get_db()

        await db.save(
            DeviceCommand(
                imei=command_req.imei,
                command=command_req.command,
                payload=payload,
                qos=qos,
                status="PUBLISHED",
                created_at=created_at_ist,
                updated_at=None,
            )
        )

        # 🔥 SAVE GEOFENCE DATA ON SUCCESSFUL API RESPONSE
        if command_req.command == "SET_GEOFENCE":
            await db.save(
                GeofenceData(
                    imei=command_req.imei,
                    geofence_number=command_req.params["geofence_number"],
                    geofence_id=command_req.params["geofence_id"],
                    coordinates=command_req.params["coordinates"],
                    created_at=created_at_ist,
                )
            )

        return {
            "status": "SENT",
            "note": "Command published to broker; device execution not confirmed",
            "imei": command_req.imei,
            "command": command_req.command,
            "qos": qos,
            "created_at": created_at_ist.isoformat(),
        }
