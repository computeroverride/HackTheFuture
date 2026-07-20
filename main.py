import time

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import load_settings
from app.services.pill_inspector import InspectionService


def main() -> None:
    settings = load_settings()

    adam = Adam6717Connection(settings)
    edgehub = None
    services = []

    try:
        adam.connect()

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

        inspection_service = InspectionService(
            settings=settings,
            adam=adam,
            edgehub=edgehub,
        )

        services = [
            inspection_service,
        ]

        
        for service in services:
            service.start()

         print()
        print("CMIO gateway is running.")
        print("DI2 button controls DO0 fan.")
        print("Thermistor AI2 has been removed from this project.")
        print("Press Ctrl+C to stop.")
        print()

        # ----------------------------------------------------
        # 5. The ONE central infinite loop in the project.
        # ----------------------------------------------------
        while True:
            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")
        print("DO0 fan remains in its current state.")

    finally:
        try:
            adam.write_do1(False)
        except Exception:
            pass

        if edgehub is not None:
            try:
                edgehub.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()