from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass
class Settings:
    # ADAM-6717
    # ========================================================

    adam_ip: str
    adam_port: int
    adam_slave_id: int

    # ========================================================
    # DI
    # ========================================================

    di0_address: int
    di2_address: int

    # ========================================================
    # DO
    # ========================================================

    do0_address: int

    # Existing older code calls this do1_address.
    # In your wiring, this points to physical DO2 because
    # DO1_ADDRESS is set to 18 in .env.
    do1_address: int

    # New clearer name for buzzer DO2.
    do2_address: int

    # ========================================================
    # AI
    # ========================================================

    ai0_address: int
    ai2_address: int
    ai4_address: int
    ai6_address: int

    # ========================================================
    # LOOP SETTINGS
    # ========================================================

    # Optional analog input for temperature
    ai_temperature_address: int
    temperature_enabled: bool

    # Timing / control
    poll_interval_seconds: float
    debounce_seconds: float
    publish_heartbeat_seconds: float

    # ========================================================
    # BUZZER SETTINGS
    # ========================================================

    buzzer_on_voltage: float
    buzzer_off_voltage: float

    # ========================================================
    # EDGEHUB
    # ========================================================

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


def _get_int(name: str, default_value: str) -> int:
    return int(_get_optional(name, default_value))


def _get_float(name: str, default_value: str) -> float:
    return float(_get_optional(name, default_value))


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

    if edgehub_enabled:
        if not edgehub_sas_token.startswith(
            "SharedAccessSignature"
        ):
            raise ValueError(
                "EDGEHUB_SAS_TOKEN must start with "
                "'SharedAccessSignature'."
            )

    # --------------------------------------------------------
    # Buzzer compatibility:
    #
    # Your physical buzzer is DO2.
    # New .env may use DO2_ADDRESS=18.
    # Older code may still use DO1_ADDRESS=18.
    #
    # This supports both.
    # --------------------------------------------------------

    do2_address = _get_int(
        "DO2_ADDRESS",
        _get_optional("DO1_ADDRESS", "18"),
    )

    do1_address = _get_int(
        "DO1_ADDRESS",
        str(do2_address),
    )

    telegram_enabled = parse_bool(os.getenv("TELEGRAM_ENABLED", "false"))

    return Settings(
        # ADAM
        adam_ip=_get_required("ADAM_IP"),
        adam_port=_get_int("ADAM_PORT", "5020"),
        adam_slave_id=_get_int("ADAM_SLAVE_ID", "1"),

        # DI
        di0_address=_get_int("DI0_ADDRESS", "0"),
        di2_address=_get_int("DI2_ADDRESS", "2"),

        # DO
        do0_address=_get_int("DO0_ADDRESS", "16"),
        do1_address=do1_address,
        do2_address=do2_address,

        # AI
        ai0_address=_get_int("AI0_ADDRESS", "30"),
        ai2_address=_get_int("AI2_ADDRESS", "34"),
        ai4_address=_get_int("AI4_ADDRESS", "38"),
        ai6_address=_get_int("AI6_ADDRESS", "42"),

        # Loop
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
