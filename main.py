import time

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import load_settings


def main() -> None:
    settings = load_settings()

    adam = Adam6717Connection(settings)
    edgehub = None

    try:
        # ----------------------------------------------------
        # 1. Connect to physical ADAM hardware.
        # ----------------------------------------------------
        adam.connect()

        # ----------------------------------------------------
        # 2. Connect to EdgeHub.
        #    ADAM control still works if EdgeHub is offline.
        # ----------------------------------------------------
        if settings.edgehub_enabled:
            try:
                edgehub = EdgeHubPublisher(settings)
                edgehub.connect_and_upload_tags()

            except Exception as error:
                print(
                    "EdgeHub is unavailable. "
                    "ADAM control will still run."
                )
                print(f"EdgeHub connection error: {error}")
                edgehub = None

        # ----------------------------------------------------
        # 3. Services have been removed.
        #    Thermistor / AI2 service removed.
        # ----------------------------------------------------

        print()
        print("CMIO gateway is running.")
        print("DI2 button controls DO0 fan.")
        print("Thermistor AI2 has been removed from this project.")
        print("Press Ctrl+C to stop.")
        print()

        # ----------------------------------------------------
        # 4. Central loop.
        # ----------------------------------------------------
        while True:
            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")
        print("DO0 fan remains in its current state.")

    finally:
        # Turn buzzer off on exit just in case.
        # write_do1() still points to physical DO2 if DO1_ADDRESS=18.
        try:
            adam.write_do1(False)
        except Exception:
            pass

        adam.close()

        if edgehub is not None:
            try:
                edgehub.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()