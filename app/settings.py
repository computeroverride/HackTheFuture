from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass
class Settings:
    # ADAM

    adam_ip: str
    adam_port: int
    adam_slave_id: int

    # DI

    di0_address: int
    di2_address: int

    # DO

    do0_address: int
    do2_address: int

    # AI

    ai0_address: int
    ai2_address: int
    ai4_address: int
    ai6_address: int

    # Camera

    camera_index: int
    camera_burst_count: int
    camera_burst_gap_seconds: float

    # Loop
    ai_temperature_address: int
    temperature_enabled: bool

    poll_interval_seconds: float
    debounce_seconds: float
    publish_heartbeat_seconds: float

    # Buzzer

    buzzer_on_voltage: float
    buzzer_off_voltage: float

    # EdgeHub

    edgehub_enabled: bool
    edgehub_node_id: str
    edgehub_sas_token: str
    edgehub_device_id: str
    edgehub_protocol_heartbeat_seconds: int


def _get_required(name: str) -> str:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise ValueError(f"Missing required .env value: {name}")

    return value.strip()


def _get_optional(name: str, default_value: str) -> str:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default_value

    return value.strip()


def _get_int(name: str, default_value: str | None = None) -> int:
    value = _get_optional(name, "") if default_value is None else _get_optional(name, default_value)
    if value == "":
        raise ValueError(f"Missing required .env value: {name}")
    return int(value)


def _get_float(name: str, default_value: str | None = None) -> float:
    value = _get_optional(name, "") if default_value is None else _get_optional(name, default_value)
    if value == "":
        raise ValueError(f"Missing required .env value: {name}")
    return float(value)


def _get_bool(name: str, default_value: str) -> bool:
    value = _get_optional(name, default_value).lower()

    return value in [
        "true",
        "1",
        "yes",
        "y",
        "on",
    ]


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)

    edgehub_enabled = _get_bool(
        "EDGEHUB_ENABLED",
        "false",
    )

    edgehub_sas_token = _get_optional(
        "EDGEHUB_SAS_TOKEN",
        "",
    )

    if edgehub_enabled and not edgehub_sas_token:
        print(
            "EDGEHUB_ENABLED is true but no valid "
            "EDGEHUB_SAS_TOKEN was provided. "
            "EdgeHub publishing will be skipped."
        )
        edgehub_enabled = False

    if edgehub_enabled and edgehub_sas_token:
        if not edgehub_sas_token.startswith(
            "SharedAccessSignature"
        ):
            print(
                "EDGEHUB_ENABLED is true but the provided "
                "EDGEHUB_SAS_TOKEN is invalid. "
                "EdgeHub publishing will be skipped."
            )
            edgehub_enabled = False

    do2_address = _get_int("DO2_ADDRESS")

    telegram_enabled = _get_bool(
        "TELEGRAM_ENABLED",
        "false",
    )

    return Settings(
        # ADAM
        adam_ip=_get_required("ADAM_IP"),
        adam_port=_get_int("ADAM_PORT"),
        adam_slave_id=_get_int("ADAM_SLAVE_ID"),

        # DI
        di0_address=_get_int("DI0_ADDRESS"),
        di2_address=_get_int("DI2_ADDRESS"),

        # DO
        do0_address=_get_int("DO0_ADDRESS"),
        do2_address=do2_address,

        # AI
        ai0_address=_get_int("AI0_ADDRESS"),
        ai2_address=_get_int("AI2_ADDRESS"),
        ai4_address=_get_int("AI4_ADDRESS"),
        ai6_address=_get_int("AI6_ADDRESS"),

        # Camera
        camera_index=_get_int("CAMERA_INDEX", "0"),
        camera_burst_count=_get_int("CAMERA_BURST_COUNT", "3"),
        camera_burst_gap_seconds=_get_float(
            "CAMERA_BURST_GAP_SECONDS",
            "0.15",
        ),

        # Loop
        ai_temperature_address=_get_int(
            "AI_TEMPERATURE_ADDRESS",
            "0",
        ),
        temperature_enabled=_get_bool(
            "TEMPERATURE_ENABLED",
            "false",
        ),
        poll_interval_seconds=_get_float(
            "POLL_INTERVAL_SECONDS",
            "0.05",
        ),
        debounce_seconds=_get_float(
            "DEBOUNCE_SECONDS",
            "0.20",
        ),
        publish_heartbeat_seconds=_get_float(
            "PUBLISH_HEARTBEAT_SECONDS",
            "3.0",
        ),

        # Buzzer
        buzzer_on_voltage=_get_float(
            "BUZZER_ON_VOLTAGE",
            "2.85",
        ),
        buzzer_off_voltage=_get_float(
            "BUZZER_OFF_VOLTAGE",
            "2.80",
        ),

        # EdgeHub
        edgehub_enabled=edgehub_enabled,
        edgehub_node_id=_get_optional(
            "EDGEHUB_NODE_ID",
            "",
        ),
        edgehub_sas_token=edgehub_sas_token,
        edgehub_device_id=_get_optional(
            "EDGEHUB_DEVICE_ID",
            "ADAM6717_IO",
        ),
        edgehub_protocol_heartbeat_seconds=_get_int(
            "EDGEHUB_PROTOCOL_HEARTBEAT_SECONDS",
            "60",
        ),
    )
