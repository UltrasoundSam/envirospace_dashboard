"""Handles connection to database"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

import pymysql

from .ingestion.settings import DatabaseSettings

logger = logging.getLogger(__name__)


def connect_to_db(settings: DatabaseSettings) -> pymysql.Connection | None:
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


def get_device_ids(connection: pymysql.Connection) -> list[str]:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT DISTINCT device_id FROM readings "
            "WHERE device_id IS NOT NULL ORDER BY device_id"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()


def get_readings(
    connection: pymysql.Connection,
    device_id: str,
    start_date: date,
    end_date: date,
) -> list[tuple[Any, ...]]:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    start_at = datetime.combine(start_date, time.min)
    end_before = datetime.combine(end_date + timedelta(days=1), time.min)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """SELECT recorded_at, temperature, humidity, noise, light_lux, pressure
               FROM readings
               WHERE device_id = %s AND recorded_at >= %s AND recorded_at < %s
               ORDER BY recorded_at""",
            (device_id, start_at, end_before),
        )
        return list(cursor.fetchall())
    finally:
        cursor.close()


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
