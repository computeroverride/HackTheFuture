from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.settings import load_settings
from integrations.telegram_notifier import TelegramNotifier


def main() -> None:
    settings = load_settings()
    notifier = TelegramNotifier(settings)

    test_image_path = (
        PROJECT_ROOT
        / "storage"
        / "telegram_button_test.jpg"
    )

    test_image_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Create a simple temporary test image.
    image = np.full(
        shape=(400, 600, 3),
        fill_value=220,
        dtype=np.uint8,
    )

    cv2.putText(
        image,
        "Telegram Button Test",
        (70, 210),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
    )

    if not cv2.imwrite(str(test_image_path), image):
        raise RuntimeError("Could not create test image.")

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅",
                    "callback_data": "test:good",
                },
                {
                    "text": "🟨",
                    "callback_data": "test:fail_defect",
                },
                {
                    "text": "🟥",
                    "callback_data": "test:fail_different",
                },
            ]
        ]
    }

    result = notifier.send_photo(
        image_path=test_image_path,
        caption=(
            "Telegram inline-button test\n\n"
            "✅ Pass   🟨 Defect   🟥 Different"
        ),
        reply_markup=keyboard,
    )

    if result:
        print("Test photo sent with inline buttons.")
    else:
        print("Telegram test failed. Check the terminal errors.")


if __name__ == "__main__":
    main()