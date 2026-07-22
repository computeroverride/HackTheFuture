from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.conveyor.constants import (
    EDGEHUB_REPORTING_INTERVAL_SECONDS,
)
from app.conveyor.helpers import format_product_id, confidence_percent


@dataclass
class ReportingWindow:
    button_triggered: bool = False
    photocell_triggered: bool = False
    completion_detected: bool = False
    reject_impact_detected: bool = False
    fan_activated: bool = False
    buzzer_activated: bool = False

    products_started: int = 0
    products_inspected: int = 0
    products_completed: int = 0
    products_rejected: int = 0
    reject_timeouts: int = 0
    feedback_count: int = 0

    def reset(self) -> None:
        self.button_triggered = False
        self.photocell_triggered = False
        self.completion_detected = False
        self.reject_impact_detected = False
        self.fan_activated = False
        self.buzzer_activated = False

        self.products_started = 0
        self.products_inspected = 0
        self.products_completed = 0
        self.products_rejected = 0
        self.reject_timeouts = 0
        self.feedback_count = 0


def set_fan(controller: object, enabled: bool) -> None:
    if enabled:
        controller.fan_relay.turn_on()
    else:
        controller.fan_relay.turn_off()

    controller.reject_fan_on = enabled
    if enabled:
        controller.window.fan_activated = True


def set_buzzer(controller: object, enabled: bool) -> None:
    if enabled:
        controller.buzzer.start_buzzing()
    else:
        controller.buzzer.stop_buzzing()

    controller.buzzer_on = enabled
    if enabled:
        controller.window.buzzer_activated = True


def start_reject_sequence(controller: object, now: float) -> None:
    # Pulse the fan/relay first; the sound sensor only starts listening
    # for the reject-bin impact once the pulse finishes (see REJECT_PULSE
    # handling in ConveyorController.run()).
    set_fan(controller, True)
    controller.process_state = "REJECT_PULSE"
    controller.reject_pulse_started_at = now
    controller.reject_sound_peaked = False
    controller.last_reject_confirmed = False


def start_product(
    controller: object,
    product_id: object,
    now: float,
) -> None:
    controller.current_product_id = format_product_id(product_id)
    controller.current_result = None
    controller.product_started_at = now
    controller.reject_started_at = None

    set_fan(controller, False)
    set_buzzer(controller, False)
    controller.buzzer_pending_product_id = ""

    controller.alarm_active = False
    controller.last_alarm_message = ""
    controller.last_reject_confirmed = False

    controller.process_state = "WAITING_FOR_PHOTOCELL"
    controller.classification_status = "PENDING"
    controller.ml_prediction = ""
    controller.ml_confidence_percent = 0.0

    controller.feedback_product_id = controller.current_product_id
    controller.feedback_status = "Pending"
    controller.actual_class = ""
    controller.feedback_received = False
    controller.ml_prediction_correct = False

    controller.last_product_event = (
        f"Product {controller.current_product_id} registered"
    )
    controller.window.button_triggered = True
    controller.window.products_started += 1

    print()
    print(
        "Button pressed -> product created: "
        f"{controller.current_product_id}"
    )
    print("Waiting for the camera photocell.")

    if controller.notifier is not None:
        controller.notifier.send(
            "🆔 New product created: "
            f"{controller.current_product_id}"
        )


def record_inspection(
    controller: object,
    result: dict[str, Any],
) -> None:
    controller.current_result = result
    controller.ml_prediction = normalise_prediction(result)
    controller.ml_confidence_percent = confidence_percent(
        float(result.get("confidence", 0.0))
    )
    controller.classification_status = (
        "GOOD" if result.get("is_pass") else "BAD"
    )

    controller.inspection_count_total += 1
    controller.window.products_inspected += 1

    if controller.ml_prediction == "good":
        controller.good_count_total += 1
    elif controller.ml_prediction == "fail_defect":
        controller.fail_defect_count_total += 1
    elif controller.ml_prediction == "fail_different":
        controller.fail_different_count_total += 1

    controller.feedback_product_id = controller.current_product_id
    controller.feedback_status = "Pending"
    controller.actual_class = ""
    controller.feedback_received = False
    controller.ml_prediction_correct = False

    controller.last_product_event = (
        f"{controller.current_product_id} classified as "
        f"{controller.ml_prediction}"
    )


def normalise_prediction(result: dict[str, Any]) -> str:
    raw_label = result.get("final_label", result.get("label", "unknown"))
    return str(raw_label).strip().lower()


def finish_product(
    controller: object,
    now: float,
    final_event: str,
) -> None:
    finished_product_id = controller.current_product_id
    controller.last_completed_product_id = finished_product_id
    controller.last_product_event = final_event

    if controller.product_started_at is not None:
        cycle_time = max(0.0, now - controller.product_started_at)
        controller.last_cycle_time_seconds = cycle_time
        controller._cycle_time_total_seconds += cycle_time
        controller._finished_cycle_count += 1

    controller.current_product_id = ""
    controller.current_result = None
    controller.product_started_at = None
    controller.reject_started_at = None
    controller.process_state = "IDLE"


def build_edgehub_snapshot(controller: object) -> dict[str, Any]:
    return {
        "adam_connected": controller.adam_connected,
        "camera_available": controller.inspector is not None,
        "product_in_progress": controller.process_state != "IDLE",
        "current_product_id": controller.current_product_id,
        "process_state": controller.process_state,
        "last_product_event": controller.last_product_event,
        "last_completed_product_id": controller.last_completed_product_id,
        "classification_status": controller.classification_status,
        "ml_prediction": controller.ml_prediction,
        "ml_confidence_percent": round(
            controller.ml_confidence_percent,
            1,
        ),
        "feedback_product_id": controller.feedback_product_id,
        "feedback_status": controller.feedback_status,
        "actual_class": controller.actual_class,
        "feedback_received": controller.feedback_received,
        "ml_prediction_correct": controller.ml_prediction_correct,
        "product_at_camera_now": controller.product_at_camera_now,
        "completion_sensor_active_now": controller.completion_sensor_active_now,
        "reject_fan_on": controller.reject_fan_on,
        "buzzer_on": controller.buzzer_on,
        "alarm_active": controller.alarm_active,
        "last_alarm_message": controller.last_alarm_message,
        "last_reject_confirmed": controller.last_reject_confirmed,
        "button_triggered_60s": controller.window.button_triggered,
        "photocell_triggered_60s": controller.window.photocell_triggered,
        "completion_detected_60s": controller.window.completion_detected,
        "reject_impact_detected_60s": controller.window.reject_impact_detected,
        "fan_activated_60s": controller.window.fan_activated,
        "buzzer_activated_60s": controller.window.buzzer_activated,
        "products_started_60s": controller.window.products_started,
        "products_inspected_60s": controller.window.products_inspected,
        "products_completed_60s": controller.window.products_completed,
        "products_rejected_60s": controller.window.products_rejected,
        "reject_timeouts_60s": controller.window.reject_timeouts,
        "feedback_count_60s": controller.window.feedback_count,
        "inspection_count_total": controller.inspection_count_total,
        "good_count_total": controller.good_count_total,
        "fail_defect_count_total": controller.fail_defect_count_total,
        "fail_different_count_total": controller.fail_different_count_total,
        "reject_confirmed_total": controller.reject_confirmed_total,
        "reject_timeout_total": controller.reject_timeout_total,
        "feedback_count_total": controller.feedback_count_total,
        "ml_correction_count_total": controller.ml_correction_count_total,
        "last_cycle_time_seconds": round(
            controller.last_cycle_time_seconds,
            1,
        ),
        "average_cycle_time_seconds": round(
            controller.average_cycle_time_seconds,
            1,
        ),
    }


def publish_edgehub_if_due(
    controller: object,
    now: float,
) -> None:
    if controller.edgehub is None:
        return

    if now - controller._last_edgehub_window_started_at < EDGEHUB_REPORTING_INTERVAL_SECONDS:
        return

    snapshot = build_edgehub_snapshot(controller)
    sent = controller.edgehub.publish_monitoring_snapshot(
        snapshot=snapshot,
        now=now,
    )

    if sent:
        controller.window.reset()
        controller._last_edgehub_window_started_at = now
