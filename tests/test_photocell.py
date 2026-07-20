from __future__ import annotations

import sys
import time
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.adam import Adam6717Connection
from app.settings import load_settings


def main() -> None:
    settings = load_settings()
    adam = Adam6717Connection(settings)
    addresses = [ 38]
    
    # Possible two-register starting addresses.
    # addresses = [
    #     30,
    #     32,
    #     34,
    #     36,
    #     38,
    #     40,
    #     42,
    # ]

    try:
        adam.connect()

        print()
        print("AI address scanner started.")
        print("Cover and uncover the photocell.")
        print("Watch which address changes.")
        print("Press Ctrl+C to stop.")
        print()

        while True:
            readings = []

            for address in addresses:
                try:
                    voltage = adam.read_ai_voltage(address)
                    readings.append(
                        f"{address}={voltage:.4f} V"
                    )
                except Exception as error:
                    readings.append(
                        f"{address}=ERROR({error})"
                    )

            print(
                " | ".join(readings),
                flush=True,
            )

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("AI address scanner stopped.")

    finally:
        adam.close()


if __name__ == "__main__":
    main()