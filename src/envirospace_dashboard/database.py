"""Handles connection to database"""

import logging
from datetime import datetime
from typing import Any

import pymysql

from .ingestion.settings import Settings

logger = logging.getLogger(__name__)


def connect_to_db(settings: Settings) -> pymysql.Connection | None:
    try:
        return pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_database,
        )
    except pymysql.Error:
        logger.exception("Error connecting to MariaDB")
        return None


def insert_reading(
    connection: pymysql.Connection,
    device_id: str,
    recorded_at: datetime,
    sensor_data: dict[str, Any],
) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO readings
               (device_id, recorded_at, temperature, humidity, noise, light_lux, pressure)  # noqa: E501
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                device_id,
                recorded_at.isoformat(),
                sensor_data.get("temperature"),
                sensor_data.get("humidity"),
                sensor_data.get("noise"),
                sensor_data.get("light"),
                sensor_data.get("pressure"),
            ),
        )
        connection.commit()
        logger.info("Inserted reading: %s @ %s", device_id, recorded_at.isoformat())
        return True
    except pymysql.Error:
        connection.rollback()
        logger.exception("Error inserting reading for %s", device_id)
        return False
    finally:
        cursor.close()
