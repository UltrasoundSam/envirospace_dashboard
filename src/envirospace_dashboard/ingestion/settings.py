"""File for handling all settings and config parameters"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def require_env(name: str) -> str:
    """Simple helper function that validates that
    env value is there, not None
    """
    value = os.getenv(name)

    if not value:
        raise ValueError(f"Missing required environment variable: {name}")

    return value


@dataclass(frozen=True)
class Settings:
    mqtt_broker: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_database: str

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        return cls(
            mqtt_broker=require_env("MQTT_BROKER"),
            mqtt_port=int(os.getenv("MQTT_PORT", "8883")),
            mqtt_username=os.getenv("MQTT_USERNAME"),
            mqtt_password=os.getenv("MQTT_PASSWORD"),
            db_host=require_env("DB_HOST"),
            db_port=int(os.getenv("DB_PORT", "3306")),
            db_user=require_env("DB_USER"),
            db_password=require_env("DB_PASSWORD"),
            db_database=require_env("DB_DATABASE"),
        )
