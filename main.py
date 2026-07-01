import time

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import load_settings
from app.services.test import ButtonFanService


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
        #    ADAM control can still work if EdgeHub is offline.
        # ----------------------------------------------------
        if settings.edgehub_enabled:
            try:
                edgehub = EdgeHubPublisher(settings)
                edgehub.connect_and_upload_tags()

            except Exception as error:
                print(
                    "EdgeHub is unavailable. "
                    "ADAM button/fan control will still run."
                )
                print(f"EdgeHub connection error: {error}")
                edgehub = None

        # ----------------------------------------------------
        # 3. Create services.
        #    Every future sensor/service goes into this list.
        # ----------------------------------------------------
        button_fan_service = ButtonFanService(
            settings=settings,
            adam=adam,
            edgehub=edgehub,
        )

        services = [
            button_fan_service,
        ]

        # Future examples:
        #
        # photocell_service = PhotocellService(
        #     settings=settings,
        #     adam=adam,
        #     edgehub=edgehub,
        # )
        # services.append(photocell_service)
        #
        # inspection_service = InspectionService(...)
        # services.append(inspection_service)

        # ----------------------------------------------------
        # 4. Start each service once.
        # ----------------------------------------------------
        for service in services:
            service.start()

        print("\nCMIO gateway is running.")
        print("Press Ctrl+C to stop.\n")

        # ----------------------------------------------------
        # 5. The ONE central infinite loop in the project.
        # ----------------------------------------------------
        while True:
            now = time.monotonic()

            for service in services:
                service.tick(now)

            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        print("\nStopped. DO0 remains in its current state.")

    finally:
        adam.close()

        if edgehub is not None:
            try:
                edgehub.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()