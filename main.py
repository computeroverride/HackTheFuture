from __future__ import annotations

from app.conveyor import ConveyorController
from app.settings import load_settings


def main() -> None:
    settings = load_settings()
    controller = ConveyorController(settings)
    controller.run()


if __name__ == "__main__":
    main()
