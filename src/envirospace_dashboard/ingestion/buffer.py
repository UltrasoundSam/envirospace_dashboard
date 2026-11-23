'''Handles data buffering so that all measurements are captured at
the same time, meaning everything can be written to database
with single write.
'''
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

BUFFER_TTL = timedelta(minutes=5)
EXPECTED_SENSORS = frozenset({"temperature", "humidity",
                              "noise", "light", "pressure"})


class ReadingBuffer:
    """Collect sensor values until a complete reading is available."""

    def __init__(self, ttl: timedelta = BUFFER_TTL) -> None:
        self._ttl = ttl
        self._readings: dict[str, dict[str, dict[str, Any]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._lock = threading.Lock()

    def add(self,
            device_id: str,
            recorded_at: datetime,
            sensor_type: str,
            value: Any) -> dict[str, Any] | None:
        timestamp = recorded_at.replace(microsecond=0).isoformat()

        with self._lock:
            sensor_data = self._readings[device_id][timestamp]
            sensor_data[sensor_type] = value
            if EXPECTED_SENSORS.issubset(sensor_data):
                del self._readings[device_id][timestamp]
                if not self._readings[device_id]:
                    del self._readings[device_id]
                return dict(sensor_data)
        return None

    def cleanup(self, now: datetime | None = None) -> int:
        now = now or datetime.now()
        cutoff = now - self._ttl
        removed = 0

        with self._lock:
            for device_id in list(self._readings):
                for timestamp in list(self._readings[device_id]):
                    try:
                        recorded_at = datetime.fromisoformat(timestamp)
                    except ValueError:
                        del self._readings[device_id][timestamp]
                        removed += 1
                        continue

                    if recorded_at < cutoff:
                        del self._readings[device_id][timestamp]
                        removed += 1

                if not self._readings[device_id]:
                    del self._readings[device_id]

        return removed

    def size(self) -> int:
        with self._lock:
            return sum(len(timestamps)
                       for timestamps in self._readings.values())


def parse_timestamp(raw_timestamp: str) -> datetime:
    parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=None)
