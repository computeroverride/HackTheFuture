import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required value in .env: {name}"
        )

    return value


def optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True)
class Settings:
    # ========================================================
    # ADAM-6717
    # ========================================================
    adam_ip: str
    adam_port: int
    adam_slave_id: int

    di2_address: int
    do0_address: int
    ai2_address: int
    do1_address: int

    # ========================================================
    # LOOP SETTINGS
    # ========================================================
    poll_interval_seconds: float
    debounce_seconds: float
    publish_heartbeat_seconds: float

    # ========================================================
    # TEMPERATURE / BUZZER SETTINGS
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
    edgehub_protocol_heartbeat_seconds: float


def load_settings() -> Settings:
    edgehub_enabled = parse_bool(
        optional_env("EDGEHUB_ENABLED", "true")
    )

    edgehub_node_id = ""
    edgehub_sas_token = ""

    if edgehub_enabled:
        edgehub_node_id = require_env("EDGEHUB_NODE_ID")
        edgehub_sas_token = require_env("EDGEHUB_SAS_TOKEN")

        if not edgehub_sas_token.startswith(
            "SharedAccessSignature"
        ):
            raise RuntimeError(
                "EDGEHUB_SAS_TOKEN must begin with "
                "'SharedAccessSignature'. Copy the complete SAS token "
                "from the EdgeHub SCADA device connection settings."
            )

    return Settings(
        # ----------------------------------------------------
        # ADAM
        # ----------------------------------------------------
        adam_ip=require_env("ADAM_IP"),
        adam_port=int(require_env("ADAM_PORT")),
        adam_slave_id=int(require_env("ADAM_SLAVE_ID")),

        di2_address=int(require_env("DI2_ADDRESS")),
        do0_address=int(require_env("DO0_ADDRESS")),
        ai2_address=int(require_env("AI2_ADDRESS")),
        do1_address=int(require_env("DO1_ADDRESS")),

        # ----------------------------------------------------
        # Loop
        # ----------------------------------------------------
        poll_interval_seconds=float(
            require_env("POLL_INTERVAL_SECONDS")
        ),
        debounce_seconds=float(
            require_env("DEBOUNCE_SECONDS")
        ),
        publish_heartbeat_seconds=float(
            require_env("PUBLISH_HEARTBEAT_SECONDS")
        ),

        # ----------------------------------------------------
        # Temperature / buzzer
        # ----------------------------------------------------
        buzzer_on_voltage=float(
            require_env("BUZZER_ON_VOLTAGE")
        ),
        buzzer_off_voltage=float(
            require_env("BUZZER_OFF_VOLTAGE")
        ),

        # ----------------------------------------------------
        # EdgeHub
        # ----------------------------------------------------
        edgehub_enabled=edgehub_enabled,
        edgehub_node_id=edgehub_node_id,
        edgehub_sas_token=edgehub_sas_token,
        edgehub_device_id=optional_env(
            "EDGEHUB_DEVICE_ID",
            "ADAM6717_IO",
        ),
        edgehub_protocol_heartbeat_seconds=float(
            optional_env(
                "EDGEHUB_PROTOCOL_HEARTBEAT_SECONDS",
                "60",
            )
        ),
    )