from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.conveyor.inspection import (
    inspect_product,
    notify_inspection_result,
    poll_telegram_feedback,
)


pytestmark = pytest.mark.unit


def test_inspect_product_fails_safely_when_camera_is_unavailable() -> None:
    controller = SimpleNamespace(inspector=None)

    result = inspect_product(controller, "P001")

    assert result == {
        "is_pass": False,
        "final_label": "inspection_unavailable",
        "confidence": 0.0,
        "saved_image": None,
    }


def test_inspect_product_normalises_result() -> None:
    inspector = Mock()
    inspector.inspect.return_value = {
        "label": "PASS",
        "confidence": "0.91",
        "image_path": "capture.jpg",
    }
    controller = SimpleNamespace(inspector=inspector)

    result = inspect_product(controller, "P002")

    assert result["is_pass"] is True
    assert result["final_label"] == "good"
    assert result["confidence"] == 0.91
    assert result["saved_image"] == "capture.jpg"


def test_inspect_product_converts_exception_to_safe_failure() -> None:
    inspector = Mock()
    inspector.inspect.side_effect = RuntimeError("camera disconnected")
    controller = SimpleNamespace(inspector=inspector)

    result = inspect_product(controller, "P003")

    assert result["is_pass"] is False
    assert result["final_label"] == "inspection_error"
    assert result["saved_image"] is None


@pytest.mark.parametrize("prediction", ["good", "fail_uncertain"])
def test_notify_inspection_result_sends_available_image_for_any_class(
    tmp_path: Path,
    prediction: str,
) -> None:
    image_path = tmp_path / "inspection.jpg"
    image_path.write_bytes(b"test-image")
    notifier = Mock()
    controller = SimpleNamespace(
        notifier=notifier,
        ml_prediction=prediction,
        ml_confidence_percent=91.0,
    )
    result = {
        "confidence": 0.91,
        "saved_image": str(image_path),
    }

    notify_inspection_result(controller, "P021", result)

    notifier.send_inspection_result.assert_called_once_with(
        product_id=21,
        predicted_label=prediction,
        confidence=0.91,
        image_path=image_path,
    )
    notifier.send.assert_not_called()


def test_notify_inspection_result_sends_text_when_image_is_missing() -> None:
    notifier = Mock()
    controller = SimpleNamespace(
        notifier=notifier,
        ml_prediction="good",
        ml_confidence_percent=88.0,
    )

    notify_inspection_result(
        controller,
        "P022",
        {"confidence": 0.88, "saved_image": None},
    )

    notifier.send.assert_called_once()
    notifier.send_inspection_result.assert_not_called()


def test_poll_telegram_feedback_updates_monitoring_state(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller._last_feedback_poll = 10.0
    controller.notifier.pop_feedback_events.return_value = [
        {
            "product_id": 5,
            "actual_label": "defect",
            "ml_correct": False,
        }
    ]

    poll_telegram_feedback(controller, now=11.1)

    controller.notifier.get_feedback_messages.assert_called_once_with()
    assert controller.feedback_product_id == "P005"
    assert controller.actual_class == "fail_defect"
    assert controller.feedback_received is True
    assert controller.ml_prediction_correct is False
    assert controller.feedback_status == "Incorrect"
    assert controller.window.feedback_count == 1
    assert controller.feedback_count_total == 1
    assert controller.ml_correction_count_total == 1


def test_poll_telegram_feedback_is_rate_limited(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller._last_feedback_poll = 10.0

    poll_telegram_feedback(controller, now=10.5)

    controller.notifier.get_feedback_messages.assert_not_called()
