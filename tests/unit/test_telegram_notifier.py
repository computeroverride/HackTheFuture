from __future__ import annotations

import pytest

from integrations.telegram_notifier import TelegramNotifier


pytestmark = pytest.mark.unit


def test_feedback_keyboard_contains_three_actual_classes() -> None:
    keyboard = TelegramNotifier._feedback_keyboard(product_id=27)

    buttons = keyboard["inline_keyboard"][0]
    assert [button["text"] for button in buttons] == ["✅", "🟨", "🟥"]
    assert [button["callback_data"] for button in buttons] == [
        "actual:27:good",
        "actual:27:fail_defect",
        "actual:27:fail_different",
    ]


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.91, "91.0%"),
        (91.0, "91.0%"),
    ],
)
def test_format_confidence(confidence: float, expected: str) -> None:
    assert TelegramNotifier._format_confidence(confidence) == expected


@pytest.mark.parametrize(
    ("configured_chat_id", "chat", "expected"),
    [
        ("123", {"id": 123}, True),
        ("123", {"id": 456}, False),
        ("@quality_channel", {"id": -1, "username": "quality_channel"}, True),
        ("@quality_channel", {"id": -1, "username": "other"}, False),
    ],
)
def test_chat_matches(
    configured_chat_id: str,
    chat: dict[str, object],
    expected: bool,
) -> None:
    assert (
        TelegramNotifier._chat_matches(chat, configured_chat_id)
        is expected
    )
