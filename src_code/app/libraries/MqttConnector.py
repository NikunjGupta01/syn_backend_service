# app/libraries/MqttConnector.py

import uuid
import logging
import time
import paho.mqtt.client as mqtt
from app.config.config import settings

logger = logging.getLogger(__name__)


class MqttConnector:
    def __init__(self):
        client_id = f"api-{settings.APP_NAME}-{uuid.uuid4().hex}"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)

        if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
            self.client.username_pw_set(
                settings.MQTT_USERNAME,
                settings.MQTT_PASSWORD
            )

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        logger.info("MQTT client initialized client_id=%s", client_id)

    def connect(self, retries: int = 10, delay: int = 3):
        """Connect to MQTT broker with retry logic"""
        for attempt in range(1, retries + 1):
            try:
                logger.info(
                    "Connecting to MQTT broker %s:%s (attempt %s/%s)",
                    settings.MQTT_BROKER,
                    settings.MQTT_PORT,
                    attempt,
                    retries,
                )

                self.client.connect(
                    settings.MQTT_BROKER,
                    settings.MQTT_PORT,
                    keepalive=60,
                )

                self.client.loop_start()

                logger.info("MQTT connected successfully")
                return

            except Exception as e:
                logger.warning(
                    "MQTT connection failed (attempt %s): %s",
                    attempt,
                    e,
                )
                time.sleep(delay)

        logger.error("MQTT connection failed after %s attempts", retries)

    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT disconnected cleanly")
        except Exception as e:
            logger.error("Error during MQTT disconnect: %s", e)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected successfully (callback)")
        else:
            logger.error("MQTT connect failed rc=%s", rc)

    def on_disconnect(self, client, userdata, rc):
        logger.warning("MQTT disconnected rc=%s", rc)


# Do NOT auto-connect here
mqtt_connector = MqttConnector()