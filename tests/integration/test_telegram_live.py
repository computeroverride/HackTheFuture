from __future__ import annotations

import base64
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.telegram]


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9WlN8xQAAAAASUVORK5CYII="
)


def test_telegram_sends_photo_with_actual_class_buttons(
    tmp_path: Path,
) -> None:
    from app.settings import load_settings
    from integrations.telegram_notifier import TelegramNotifier

    settings = load_settings()
    if not settings.telegram_enabled:
        pytest.skip("TELEGRAM_ENABLED is false")
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        pytest.skip("Telegram bot token or chat ID is missing")

    image_path = tmp_path / "telegram_pytest.png"
    image_path.write_bytes(ONE_PIXEL_PNG)

    notifier = TelegramNotifier(settings)
    message = notifier.send_photo(
        image_path=image_path,
        caption=(
            "pytest Telegram integration test\n\n"
            "Select the actual class:\n"
            "✅ Pass / Good   🟨 Defect   🟥 Different"
        ),
        reply_markup=notifier._feedback_keyboard(product_id=999),
    )

    assert message is not None
    assert int(message.get("message_id", 0)) > 0
