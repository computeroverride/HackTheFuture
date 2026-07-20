from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.conveyor.helpers import (
    confidence_percent,
    extract_product_number,
    format_product_id,
    normalise_label,
)
from app.services.pill_inspector import PillInspector
from integrations.telegram_notifier import TelegramNotifier


def inspect_product(
    controller: object,
    product_id: str,
) -> dict[str, Any]:
    if controller.inspector is None:
        return {
            "is_pass": False,
            "final_label": "inspection_unavailable",
            "confidence": 0.0,
            "saved_image": None,
        }

    try:
        result = controller.inspector.inspect(product_id)

        if not isinstance(result, dict):
            raise TypeError(
                "PillInspector.inspect() must return a dict."
            )

        label = normalise_label(
            result.get("final_label", result.get("label", "unknown"))
        )
        confidence = float(result.get("confidence", 0.0))
        saved_image = result.get(
            "saved_image",
            result.get("image_path"),
        )
        is_pass = bool(result.get("is_pass", label == "good"))

        return {
            **result,
            "is_pass": is_pass,
            "final_label": label,
            "confidence": confidence,
            "saved_image": saved_image,
        }

    except Exception as error:
        print(f"Inspection failed: {error}")
        return {
            "is_pass": False,
            "final_label": "inspection_error",
            "confidence": 0.0,
            "saved_image": None,
        }


def _format_confidence(confidence: float) -> str:
    if 0 <= confidence <= 1:
        return f"{confidence:.1%}"
    return f"{confidence:.1f}%"


def _feedback_keyboard(product_id: int) -> dict[str, object]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅",
                    "callback_data": f"actual:{product_id}:good",
                },
                {
                    "text": "🟨",
                    "callback_data": f"actual:{product_id}:fail_defect",
                },
                {
                    "text": "🟥",
                    "callback_data": f"actual:{product_id}:fail_different",
                },
            ]
        ]
    }


def notify_inspection_result(
    controller: object,
    product_id: str,
    result: dict[str, Any],
) -> None:
    if controller.notifier is None:
        return

    product_number = extract_product_number(product_id)
    saved_image = result.get("saved_image", result.get("image_path"))

    if product_number is None or not saved_image:
        controller.notifier.send(
            f"Inspection completed for {product_id}\n"
            f"ML prediction: {controller.ml_prediction}\n"
            f"Confidence: {controller.ml_confidence_percent:.1f}%\n"
            "No feedback image was available."
        )
        return

    image_path = Path(saved_image)
    if not image_path.exists():
        print(f"Telegram feedback image does not exist: {image_path}")
        return

    try:
        controller.notifier.send_inspection_result(
            product_id=product_number,
            predicted_label=controller.ml_prediction,
            confidence=float(result.get("confidence", 0.0)),
            image_path=image_path,
        )
    except Exception as error:
        print(f"Telegram inspection send failed: {error}")


def poll_telegram_feedback(
    controller: object,
    now: float,
) -> None:
    if controller.notifier is None:
        return

    if now - controller._last_feedback_poll < 1.0:
        return

    controller._last_feedback_poll = now

    try:
        controller.notifier.get_feedback_messages()
        pop_events = getattr(controller.notifier, "pop_feedback_events", None)
        if not callable(pop_events):
            return

        for event in pop_events():
            product_id = format_product_id(event.get("product_id", ""))
            actual_label = normalise_label(
                event.get("actual_label", "unknown")
            )
            ml_correct = bool(event.get("ml_correct", False))

            controller.feedback_product_id = product_id
            controller.actual_class = actual_label
            controller.feedback_received = True
            controller.ml_prediction_correct = ml_correct
            controller.feedback_status = (
                "Correct" if ml_correct else "Incorrect"
            )

            controller.window.feedback_count += 1
            controller.feedback_count_total += 1

            if not ml_correct:
                controller.ml_correction_count_total += 1

            controller.last_product_event = (
                f"Human feedback recorded for {product_id}: "
                f"{actual_label}"
            )

            print(
                "Telegram feedback recorded for monitoring -> "
                f"product={product_id}, "
                f"actual={actual_label}, "
                f"correct={ml_correct}"
            )

    except Exception as error:
        print(f"Telegram feedback polling error: {error}")
