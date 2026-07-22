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

    # Camera

    camera_index: int
    camera_burst_count: int
    camera_burst_gap_seconds: float

    # Loop

    poll_interval_seconds: float

    # Buzzer

    buzzer_on_voltage: float
    buzzer_off_voltage: float

    # Telegram

    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_feedback_chat_id: str

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


def _get_int(name: str) -> int:
    return int(_get_required(name))


def _get_float(name: str) -> float:
    return float(_get_required(name))


def _get_bool(name: str) -> bool:
    value = _get_required(name).lower()

    return value in [
        "true",
        "1",
        "yes",
        "y",
        "on",
    ]


def load_settings() -> Settings:
    load_dotenv(ENV_PATH)

    edgehub_enabled = _get_bool("EDGEHUB_ENABLED")

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

    telegram_enabled = _get_bool("TELEGRAM_ENABLED")

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

        # Camera
        camera_index=_get_int("CAMERA_INDEX"),
        camera_burst_count=_get_int("CAMERA_BURST_COUNT"),
        camera_burst_gap_seconds=_get_float("CAMERA_BURST_GAP_SECONDS"),

        # Loop
        poll_interval_seconds=_get_float("POLL_INTERVAL_SECONDS"),

        # Buzzer
        buzzer_on_voltage=_get_float("BUZZER_ON_VOLTAGE"),
        buzzer_off_voltage=_get_float("BUZZER_OFF_VOLTAGE"),

        # Telegram
        telegram_enabled=telegram_enabled,
        telegram_bot_token=_get_optional(
            "TELEGRAM_BOT_TOKEN",
            "",
        ),
        telegram_chat_id=_get_optional(
            "TELEGRAM_CHAT_ID",
            "",
        ),
        telegram_feedback_chat_id=_get_optional(
            "TELEGRAM_FEEDBACK_CHAT_ID",
            "",
        ),

        # EdgeHub
        edgehub_enabled=edgehub_enabled,
        edgehub_node_id=_get_optional(
            "EDGEHUB_NODE_ID",
            "",
        ),
        edgehub_sas_token=edgehub_sas_token,
        edgehub_device_id=_get_required("EDGEHUB_DEVICE_ID"),
        edgehub_protocol_heartbeat_seconds=_get_int(
            "EDGEHUB_PROTOCOL_HEARTBEAT_SECONDS",
        ),
    )
