import time

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import load_settings
from app.services.button_fan_service import ButtonFanService
from app.services.temperature_buzzer_service import (
    TemperatureBuzzerService,
)


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
        # 3. Create services.
        #    Every service has start() and tick().
        # ----------------------------------------------------
        button_fan_service = ButtonFanService(
            settings=settings,
            adam=adam,
            edgehub=edgehub,
        )

        temperature_buzzer_service = TemperatureBuzzerService(
            settings=settings,
            adam=adam,
            edgehub=edgehub,
        )

        services = [
            button_fan_service,
            temperature_buzzer_service,
        ]

        # ----------------------------------------------------
        # 4. Start each service once.
        # ----------------------------------------------------
        for service in services:
            service.start()

        print()
        print("CMIO gateway is running.")
        print("DI2 button controls DO0 fan.")
        print("AI2 voltage controls DO1 buzzer.")
        print("Press Ctrl+C to stop.")
        print()

        # ----------------------------------------------------
        # 5. One central infinite loop.
        # ----------------------------------------------------
        while True:
            now = time.monotonic()

            for service in services:
                service.tick(now)

            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")
        print("DO0 fan remains in its current state.")

    finally:
        # Safety: turn buzzer off on exit.
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