from __future__ import annotations

from typing import TYPE_CHECKING

from app.adam import Adam6717Connection
from app.conveyor.constants import (
    AI_SCAN_ADDRESSES,
    PHOTOCELL_ADDRESS,
    REJECT_SOUND_THRESHOLD_VOLTAGE,
)

if TYPE_CHECKING:
    from app.conveyor.controller import ConveyorController


def read_ai_scan(adam: Adam6717Connection) -> dict[int, float]:
    readings: dict[int, float] = {}

    for address in AI_SCAN_ADDRESSES:
        readings[address] = adam.read_ai_voltage(address)

    if PHOTOCELL_ADDRESS not in readings:
        raise RuntimeError(
            f"Photocell address {PHOTOCELL_ADDRESS} "
            "was not returned by the AI scan."
        )

    return readings


def derive_sound_activated(
    settings: object,
    adam: Adam6717Connection,
    readings: dict[int, float],
) -> bool:
    sound_address = int(settings.ai0_address)

    if sound_address in readings:
        sound_voltage = readings[sound_address]
    else:
        sound_voltage = adam.read_ai_voltage(sound_address)

    return abs(float(sound_voltage)) >= REJECT_SOUND_THRESHOLD_VOLTAGE


def refresh_current_outputs(controller: "ConveyorController") -> None:
    controller.reject_fan_on = bool(controller.adam.read_do0())
    controller.buzzer_on = bool(controller.adam.read_do2())

    if controller.reject_fan_on:
        controller.window.fan_activated = True

    if controller.buzzer_on:
        controller.window.buzzer_activated = True


def normalise_label(label: object) -> str:
    value = str(label or "unknown").strip().lower()
    aliases = {
        "pass": "good",
        "passed": "good",
        "different": "fail_different",
        "defect": "fail_defect",
        "defective": "fail_defect",
    }
    return aliases.get(value, value)


def extract_product_number(product_id: object) -> int | None:
    if isinstance(product_id, int):
        return product_id

    matches = __import__("re").findall(r"\d+", str(product_id))
    return int(matches[-1]) if matches else None


def format_product_id(product_id: object) -> str:
    try:
        return f"P{int(product_id):03d}"
    except (TypeError, ValueError):
        value = str(product_id)
        matches = __import__("re").findall(r"\d+", value)
        if matches:
            return f"P{int(matches[-1]):03d}"
        return value


def confidence_percent(confidence: float) -> float:
    if 0.0 <= confidence <= 1.0:
        return confidence * 100.0
    return confidence
