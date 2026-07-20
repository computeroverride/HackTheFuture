from __future__ import annotations

import sys
import time
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.edgehub import EdgeHubPublisher
from app.settings import load_settings


def main() -> None:
    settings = load_settings()

    if not settings.edgehub_enabled:
        raise RuntimeError(
            "EDGEHUB_ENABLED is false in .env."
        )

    edgehub = EdgeHubPublisher(settings)

    try:
        print("Connecting and uploading tag configuration...")
        edgehub.connect_and_upload_tags()

        print("Sending sample product-created event...")
        edgehub.publish_product_created(
            product_id="P999",
        )
        time.sleep(1)

        print("Sending sample ML inspection...")
        edgehub.publish_inspection(
            product_id="P999",
            predicted_label="fail_defect",
            confidence=0.91,
            is_pass=False,
            inspection_count=1,
            good_count=0,
            faulty_count=1,
            image_path="storage/predictions/P999.jpg",
            process_state="MOVING_TO_REJECT",
        )
        time.sleep(1)

        print("Sending sample Telegram feedback...")
        edgehub.publish_feedback(
            product_id="P999",
            predicted_label="fail_defect",
            actual_label="fail_different",
            ml_correct=False,
            confidence=0.91,
        )

        print()
        print("Sample EdgeHub events sent.")
        print("Check the device tags for product P999.")

    finally:
        edgehub.disconnect()


if __name__ == "__main__":
    main()