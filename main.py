import time

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import load_settings
from app.services.pill_inspector import PillInspector


def main() -> None:
    settings = load_settings()

    adam = Adam6717Connection(settings)
    edgehub = None
    services = []
    adam_connected = False

    try:
        try:
            adam.connect()
            adam_connected = True
        except Exception as error:
            print("ADAM-6717 is unavailable. Starting in offline/demo mode.")
            print(f"ADAM connection error: {error}")
            adam_connected = False

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

        if adam_connected:
            try:
                inspection_service = PillInspector()
                services = [inspection_service]
            except Exception as error:
                print("Vision inspection is unavailable. Continuing without it.")
                print(f"Inspection error: {error}")

        for service in services:
            if hasattr(service, "start"):
                service.start()

        print()
        print("CMIO gateway is running.")
        if adam_connected:
            print("ADAM control is active.")
        else:
            print("ADAM control is disabled; running in offline mode.")
        print("Press Ctrl+C to stop.")
        print()

      
        # The central infinite loop in the project.
        
        while True:
            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")
        print("DO0 fan remains in its current state.")

    finally:
        try:
            adam.write_do2(False)
        except Exception:
            pass

        if edgehub is not None:
            try:
                edgehub.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()