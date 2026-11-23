"""MQTT to MariaDB subscriber for envirospace sensor data."""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

import paho.mqtt.client as mqtt
import pymysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# MariaDB Configuration (add these to your .env)
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_DATABASE")

# Buffer to collect readings by device_id and timestamp
# Structure: {device_id: {timestamp: {sensor_type: value}}}
readings_buffer = defaultdict(lambda: defaultdict(dict))
# Global database connection (will be set after connection)
conn = None


def connect_to_db():
    """Create and return a MariaDB connection."""
    global conn
    try:
        new_conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE
        )
        conn = new_conn
        return new_conn
    except pymysql.Error as e:
        print(f"Error connecting to MariaDB: {e}")
        return None


def insert_reading(device_id, recorded_at, sensor_data):
    """Insert a complete set of readings into the database."""
    global conn
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO readings
               (device_id, recorded_at, temperature, humidity, noise, light_lux, pressure)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                device_id,
                recorded_at,
                sensor_data.get("temperature"),
                sensor_data.get("humidity"),
                sensor_data.get("noise"),
                sensor_data.get("light"),
                sensor_data.get("pressure")
            )
        )
        conn.commit()
        print(f"Inserted: {device_id} @ {recorded_at}")
    except pymysql.Error as e:
        print(f"Error inserting reading: {e}")
        conn.rollback()
    finally:
        cursor.close()


def on_message(client, userdata, msg):
    """Handle incoming MQTT messages."""
    try:
        print(f"Received: {msg.topic}")  # Debug: show incoming topic

        # Parse topic: envirospace/room101/temperature
        topic_parts = msg.topic.split("/")
        if len(topic_parts) < 3:
            print(f"Unexpected topic format: {msg.topic}")
            return

        device_id = topic_parts[1]  # e.g., "room101"
        sensor_type = topic_parts[2]  # e.g., "temperature"

        # Parse payload
        payload = json.loads(msg.payload)
        raw_timestamp = payload["timestamp"]
        value = payload["value"]

        # Normalize timestamp to seconds (truncate microseconds) and strip timezone
        # ISO format: 2024-01-15T10:30:00.123456+00:00 -> 2024-01-15T10:30:00
        timestamp = datetime.fromisoformat(raw_timestamp).replace(microsecond=0, tzinfo=None).isoformat()

        # Store in buffer
        readings_buffer[device_id][timestamp][sensor_type] = value
        print(f"Buffered: {device_id}/{timestamp}/{sensor_type} = {value}")  # Debug

        # Check if we have all expected sensors for this timestamp
        # Expected: temperature, humidity, pressure, light, noise
        # But we only need: temperature, humidity, noise, light_lux
        expected_sensors = {"temperature", "humidity", "noise", "light", "pressure"}
        received_sensors = set(readings_buffer[device_id][timestamp].keys())

        # If we have all the sensors we need
        if expected_sensors.issubset(received_sensors):
            # Insert and remove from buffer
            insert_reading(device_id, timestamp, readings_buffer[device_id][timestamp])
            del readings_buffer[device_id][timestamp]

    except json.JSONDecodeError:
        print(f"Invalid JSON payload: {msg.payload}")
    except Exception as e:
        print(f"Error processing message: {e}")


def cleanup_old_buffer_entries():
    """Remove buffer entries older than 5 minutes to prevent memory growth."""
    current_time = time.time()
    cutoff_time = current_time - 300  # 5 minutes

    for device_id in list(readings_buffer.keys()):
        for timestamp_str in list(readings_buffer[device_id].keys()):
            # Convert ISO timestamp to epoch time for comparison
            # This is a simplified approach; in production you'd parse the ISO string
            pass  # We'll skip this for now and rely on successful insertions


# Connect to MQTT
client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv311
)
client.tls_set()
if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

# Connect to database
connect_to_db()
if conn is None:
    print("Failed to connect to database. Exiting.")
    sys.exit(1)

# Subscribe to all envirospace topics
client.subscribe("envirospace/#", qos=1)
client.loop_start()

print("MQTT to MariaDB subscriber started. Listening to envirospace/#")

try:
    while True:
        time.sleep(1)
        # Periodically clean up old buffer entries
        if len(readings_buffer) > 0:
            cleanup_old_buffer_entries()
except KeyboardInterrupt:
    print("Shutting down...")
    client.loop_stop()
    client.disconnect()
    if conn:
        conn.close()
    sys.exit(0)
