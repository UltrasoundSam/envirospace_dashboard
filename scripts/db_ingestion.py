"""MQTT to MariaDB subscriber for EnviroSpace sensor data."""

import logging
import os
import signal
import threading
from datetime import timedelta
from typing import Any

from envirospace_dashboard import IngestionSubscriber, Settings
from envirospace_dashboard.database import connect_to_db

BUFFER_TTL = timedelta(minutes=5)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    # Import config settings from .env file
    try:
        settings = Settings.from_env()
    except (ValueError, OSError) as error:
        logger.error("%s", error)
        return 1

    # Connect to db
    connection = connect_to_db(settings)
    if connection is None:
        logger.error("Failed to connect to MariaDB")
        return 1

    # Create subscriber
    subscriber = IngestionSubscriber(settings, connection, BUFFER_TTL)

    # Register shutdown handlers
    stop_requested = threading.Event()

    def request_stop(signum: int, frame: Any) -> None:
        del signum, frame
        stop_requested.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    # Start the subscriber running until asked to stop
    try:
        subscriber.start()
        while not stop_requested.wait(timeout=1):
            subscriber.cleanup_buffer()
    finally:
        subscriber.stop()

    logger.info("MQTT subscriber stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
