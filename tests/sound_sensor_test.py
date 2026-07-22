from __future__ import annotations

import time

from app.adam import Adam6717Connection
from app.conveyor.constants import (
    REJECT_SOUND_HIGH_THRESHOLD_VOLTAGE,
    REJECT_SOUND_LOW_THRESHOLD_VOLTAGE,
)
from app.settings import load_settings


def main() -> None:
    settings = load_settings()
    adam = Adam6717Connection(settings)
    adam.connect()

    print(f"Reading sound sensor at AI0 (address {settings.ai0_address}).")
    print(
        "Current thresholds (app/conveyor/constants.py): "
        f"HIGH={REJECT_SOUND_HIGH_THRESHOLD_VOLTAGE}, "
        f"LOW={REJECT_SOUND_LOW_THRESHOLD_VOLTAGE}"
    )
    print(
        "An impact is confirmed once voltage rises above HIGH, "
        "then falls back below LOW."
    )
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            voltage = adam.read_ai_voltage(settings.ai0_address)

            if voltage >= REJECT_SOUND_HIGH_THRESHOLD_VOLTAGE:
                state = "LOUD"
            elif voltage <= REJECT_SOUND_LOW_THRESHOLD_VOLTAGE:
                state = "idle"
            else:
                state = "settling"

            print(f"voltage={voltage:+.4f} V  [{state}]")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        adam.close()


if __name__ == "__main__":
    main()
