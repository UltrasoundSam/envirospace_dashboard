"""Handles orchestration - getting data from MQTT and putting
it in database
"""

import json
import logging
from datetime import timedelta
from typing import Any

import paho.mqtt.client as mqtt
import pymysql

from envirospace_dashboard import ReadingBuffer, Settings
from envirospace_dashboard.database import insert_reading
from envirospace_dashboard.ingestion.buffer import parse_timestamp

logger = logging.getLogger(__name__)

MQTT_TOPIC = "envirospace/#"
API_VERSION = mqtt.CallbackAPIVersion.VERSION2  # type: ignore


class IngestionSubscriber:
    def __init__(
        self, settings: Settings, connection: pymysql.Connection, TTL: timedelta
    ) -> None:
        self.settings = settings
        self.connection = connection
        self.buffer = ReadingBuffer(TTL)
        self.client = mqtt.Client(
            callback_api_version=API_VERSION,
            protocol=mqtt.MQTTv311,
        )
        self.client.tls_set()
        if settings.mqtt_username and settings.mqtt_password:
            self.client.username_pw_set(
                settings.mqtt_username,
                settings.mqtt_password,
            )
        self.client.on_message = self.on_message

    def start(self) -> None:
        self.client.connect(
            self.settings.mqtt_broker,
            self.settings.mqtt_port,
            keepalive=60,
        )
        self.client.subscribe(MQTT_TOPIC, qos=1)
        self.client.loop_start()
        logger.info("MQTT subscriber started. Listening to %s", MQTT_TOPIC)

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
        self.connection.close()

    def on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        # Client and user data required in Paho callback sigs
        # But don't need them here
        del client, userdata
        logger.debug("Received MQTT topic: %s", msg.topic)

        topic = parse_topic(msg.topic)
        if topic is None:
            logger.warning("Unexpected topic format: %s", msg.topic)
            return
        device_id, sensor_type = topic

        try:
            payload = json.loads(msg.payload)
            raw_timestamp = payload["timestamp"]
            value = payload["value"]
            recorded_at = parse_timestamp(raw_timestamp)
        except json.JSONDecodeError, KeyError, TypeError, ValueError:
            logger.exception("Invalid MQTT payload on topic %s", msg.topic)
            return

        complete_reading = self.buffer.add(
            device_id,
            recorded_at,
            sensor_type,
            value,
        )
        if complete_reading is not None:
            insert_reading(
                self.connection,
                device_id,
                recorded_at,
                complete_reading,
            )

    def cleanup_buffer(self) -> None:
        removed = self.buffer.cleanup()
        if removed:
            logger.info("Removed %d expired buffered readings", removed)


def parse_topic(topic: str) -> tuple[str, str] | None:
    topic_parts = topic.split("/")
    if len(topic_parts) != 3 or topic_parts[0] != "envirospace":
        return None
    return topic_parts[1], topic_parts[2]
