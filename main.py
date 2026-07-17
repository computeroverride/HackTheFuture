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
                print("EdgeHub is unavailable. Conveyor test will still run.")
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
        print("CMIO conveyor inspection test is running.")
        print("Press Ctrl+C to stop.")
        print()

        while True:
            now = time.monotonic()

            for service in services:
                service.tick(now)

            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")

    finally:
        for service in services:
            safe_shutdown = getattr(service, "safe_shutdown", None)
            if safe_shutdown is not None:
                safe_shutdown()

        adam.close()

        if edgehub is not None:
            try:
                edgehub.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()