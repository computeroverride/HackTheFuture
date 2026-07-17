import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required value in .env: {name}")
    return value


def optional_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)).strip())


def optional_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)).strip())


def optional_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # ADAM-6717
    adam_ip: str
    adam_port: int
    adam_slave_id: int

    # Digital inputs
    di_camera_sensor_address: int
    di_end_sensor_address: int
    di_button_address: int

    # Digital outputs
    do_conveyor_address: int
    do_servo_trigger_address: int
    do_buzzer_address: int
    do_fan_address: int

    # Optional analog input for temperature
    ai_temperature_address: int
    temperature_enabled: bool

    # Timing / control
    poll_interval_seconds: float
    debounce_seconds: float
    publish_heartbeat_seconds: float
    reject_delay_seconds: float
    end_delay_seconds: float
    end_match_tolerance_seconds: float
    servo_trigger_pulse_seconds: float
    buzzer_pulse_seconds: float

    # Camera / ML
    camera_index: int
    camera_burst_count: int
    camera_burst_gap_seconds: float
    ml_mode: str
    fake_fault_every_n: int

    # Temperature thresholds
    temp_fan_on_c: float
    temp_fan_off_c: float
    temp_danger_c: float

    # Telegram
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str

    # EdgeHub
    edgehub_enabled: bool
    edgehub_node_id: str
    edgehub_sas_token: str
    edgehub_device_id: str
    edgehub_protocol_heartbeat_seconds: float


def load_settings() -> Settings:
    edgehub_enabled = parse_bool(os.getenv("EDGEHUB_ENABLED", "true"))
    edgehub_node_id = ""
    edgehub_sas_token = ""

    if edgehub_enabled:
        edgehub_node_id = require_env("EDGEHUB_NODE_ID")
        edgehub_sas_token = require_env("EDGEHUB_SAS_TOKEN")
        if not edgehub_sas_token.startswith("SharedAccessSignature"):
            raise RuntimeError(
                "EDGEHUB_SAS_TOKEN must begin with 'SharedAccessSignature'. "
                "Copy the complete SAS token from the SCADA device Connection Setting."
            )

    telegram_enabled = parse_bool(os.getenv("TELEGRAM_ENABLED", "false"))

    return Settings(
        adam_ip=require_env("ADAM_IP"),
        adam_port=int(require_env("ADAM_PORT")),
        adam_slave_id=int(require_env("ADAM_SLAVE_ID")),

        # Keep backward-compatible defaults with your current DI2/DO0 setup.
        di_camera_sensor_address=optional_int("DI_CAMERA_SENSOR_ADDRESS", 0),
        di_end_sensor_address=optional_int("DI_END_SENSOR_ADDRESS", 1),
        di_button_address=optional_int("DI_BUTTON_ADDRESS", optional_int("DI2_ADDRESS", 2)),

        do_conveyor_address=optional_int("DO_CONVEYOR_ADDRESS", optional_int("DO0_ADDRESS", 16)),
        do_servo_trigger_address=optional_int("DO_SERVO_TRIGGER_ADDRESS", 17),
        do_buzzer_address=optional_int("DO_BUZZER_ADDRESS", 18),
        do_fan_address=optional_int("DO_FAN_ADDRESS", 19),

        ai_temperature_address=optional_int("AI_TEMPERATURE_ADDRESS", 0),
        temperature_enabled=parse_bool(os.getenv("TEMPERATURE_ENABLED", "false")),

        poll_interval_seconds=optional_float("POLL_INTERVAL_SECONDS", 0.05),
        debounce_seconds=optional_float("DEBOUNCE_SECONDS", 0.20),
        publish_heartbeat_seconds=optional_float("PUBLISH_HEARTBEAT_SECONDS", 3.0),
        reject_delay_seconds=optional_float("REJECT_DELAY_SECONDS", 3.5),
        end_delay_seconds=optional_float("END_DELAY_SECONDS", 5.0),
        end_match_tolerance_seconds=optional_float("END_MATCH_TOLERANCE_SECONDS", 0.8),
        servo_trigger_pulse_seconds=optional_float("SERVO_TRIGGER_PULSE_SECONDS", 0.20),
        buzzer_pulse_seconds=optional_float("BUZZER_PULSE_SECONDS", 0.40),

        camera_index=optional_int("CAMERA_INDEX", 0),
        camera_burst_count=optional_int("CAMERA_BURST_COUNT", 3),
        camera_burst_gap_seconds=optional_float("CAMERA_BURST_GAP_SECONDS", 0.10),
        ml_mode=optional_str("ML_MODE", "fake_alternate"),
        fake_fault_every_n=optional_int("FAKE_FAULT_EVERY_N", 3),

        temp_fan_on_c=optional_float("TEMP_FAN_ON_C", 40.0),
        temp_fan_off_c=optional_float("TEMP_FAN_OFF_C", 35.0),
        temp_danger_c=optional_float("TEMP_DANGER_C", 60.0),

        telegram_enabled=telegram_enabled,
        telegram_bot_token=optional_str("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=optional_str("TELEGRAM_CHAT_ID"),

        edgehub_enabled=edgehub_enabled,
        edgehub_node_id=edgehub_node_id,
        edgehub_sas_token=edgehub_sas_token,
        edgehub_device_id=require_env("EDGEHUB_DEVICE_ID"),
        edgehub_protocol_heartbeat_seconds=optional_float(
            "EDGEHUB_PROTOCOL_HEARTBEAT_SECONDS", 60.0
        ),
    )
