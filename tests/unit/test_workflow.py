from __future__ import annotations

from typing import Any

import pytest

from app.conveyor.constants import EDGEHUB_REPORTING_INTERVAL_SECONDS
from app.conveyor.workflow import (
    ReportingWindow,
    build_edgehub_snapshot,
    finish_product,
    publish_edgehub_if_due,
    record_inspection,
    set_buzzer,
    set_fan,
    start_product,
)


pytestmark = pytest.mark.unit


def test_reporting_window_reset_clears_only_window_values() -> None:
    window = ReportingWindow(
        button_triggered=True,
        photocell_triggered=True,
        completion_detected=True,
        reject_impact_detected=True,
        fan_activated=True,
        buzzer_activated=True,
        products_started=2,
        products_inspected=2,
        products_completed=1,
        products_rejected=1,
        reject_timeouts=1,
        feedback_count=2,
    )

    window.reset()

    assert window == ReportingWindow()


def test_set_fan_updates_output_and_latches_activation(
    controller_factory,
) -> None:
    controller = controller_factory()

    set_fan(controller, True)

    controller.fan_relay.turn_on.assert_called_once_with()
    assert controller.reject_fan_on is True
    assert controller.window.fan_activated is True

    set_fan(controller, False)

    controller.fan_relay.turn_off.assert_called_once_with()
    assert controller.reject_fan_on is False
    assert controller.window.fan_activated is True


def test_set_buzzer_updates_output_and_latches_activation(
    controller_factory,
) -> None:
    controller = controller_factory()

    set_buzzer(controller, True)

    controller.buzzer.start_buzzing.assert_called_once_with()
    assert controller.buzzer_on is True
    assert controller.window.buzzer_activated is True

    set_buzzer(controller, False)

    controller.buzzer.stop_buzzing.assert_called_once_with()
    assert controller.buzzer_on is False


def test_start_product_initialises_monitoring_state(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller.alarm_active = True
    controller.last_alarm_message = "old alarm"

    start_product(controller, "product-7", now=12.5)

    assert controller.current_product_id == "P007"
    assert controller.process_state == "WAITING_FOR_PHOTOCELL"
    assert controller.product_started_at == 12.5
    assert controller.classification_status == "PENDING"
    assert controller.feedback_status == "Pending"
    assert controller.alarm_active is False
    assert controller.window.button_triggered is True
    assert controller.window.products_started == 1
    controller.notifier.send.assert_called_once()


def test_record_good_inspection_updates_counters(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller.current_product_id = "P003"

    record_inspection(
        controller,
        {
            "is_pass": True,
            "final_label": "good",
            "confidence": 0.934,
        },
    )

    assert controller.ml_prediction == "good"
    assert controller.ml_confidence_percent == pytest.approx(93.4)
    assert controller.classification_status == "GOOD"
    assert controller.inspection_count_total == 1
    assert controller.good_count_total == 1
    assert controller.window.products_inspected == 1


@pytest.mark.parametrize(
    ("label", "counter_name"),
    [
        ("fail_defect", "fail_defect_count_total"),
        ("fail_different", "fail_different_count_total"),
    ],
)
def test_record_failed_inspection_updates_class_counter(
    controller_factory,
    label: str,
    counter_name: str,
) -> None:
    controller = controller_factory()
    controller.current_product_id = "P004"

    record_inspection(
        controller,
        {
            "is_pass": False,
            "final_label": label,
            "confidence": 87.0,
        },
    )

    assert controller.classification_status == "BAD"
    assert getattr(controller, counter_name) == 1


def test_finish_product_records_cycle_time_and_returns_to_idle(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller.current_product_id = "P012"
    controller.current_result = {"is_pass": True}
    controller.product_started_at = 10.0
    controller.process_state = "GOOD_AWAITING_COMPLETION"

    finish_product(
        controller,
        now=17.25,
        final_event="Good completion confirmed",
    )

    assert controller.last_completed_product_id == "P012"
    assert controller.last_cycle_time_seconds == pytest.approx(7.25)
    assert controller.average_cycle_time_seconds == pytest.approx(7.25)
    assert controller.current_product_id == ""
    assert controller.current_result is None
    assert controller.process_state == "IDLE"


def test_build_edgehub_snapshot_contains_product_monitoring_data(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller.process_state = "INSPECTING"
    controller.current_product_id = "P015"
    controller.ml_prediction = "good"
    controller.ml_confidence_percent = 93.46
    controller.window.products_started = 1
    controller.window.photocell_triggered = True

    snapshot = build_edgehub_snapshot(controller)

    assert snapshot["product_in_progress"] is True
    assert snapshot["current_product_id"] == "P015"
    assert snapshot["process_state"] == "INSPECTING"
    assert snapshot["ml_prediction"] == "good"
    assert snapshot["ml_confidence_percent"] == 93.5
    assert snapshot["products_started_60s"] == 1
    assert snapshot["photocell_triggered_60s"] is True
    assert "saved_image" not in snapshot
    assert "image_path" not in snapshot
    assert "photocell_voltage" not in snapshot
    assert "sound_voltage" not in snapshot


def test_publish_edgehub_if_due_waits_for_full_interval(
    controller_factory,
) -> None:
    controller = controller_factory()

    publish_edgehub_if_due(
        controller,
        now=100.0 + EDGEHUB_REPORTING_INTERVAL_SECONDS - 0.01,
    )

    controller.edgehub.publish_monitoring_snapshot.assert_not_called()


def test_publish_edgehub_if_due_sends_and_resets_window(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller.window.products_started = 2
    controller.window.button_triggered = True
    controller.edgehub.publish_monitoring_snapshot.return_value = True
    now = 100.0 + EDGEHUB_REPORTING_INTERVAL_SECONDS

    publish_edgehub_if_due(controller, now=now)

    controller.edgehub.publish_monitoring_snapshot.assert_called_once()
    call_kwargs: dict[str, Any] = (
        controller.edgehub.publish_monitoring_snapshot.call_args.kwargs
    )
    assert call_kwargs["now"] == now
    assert call_kwargs["snapshot"]["products_started_60s"] == 2
    assert controller.window == ReportingWindow()
    assert controller._last_edgehub_window_started_at == now


def test_publish_edgehub_if_due_keeps_window_after_failed_send(
    controller_factory,
) -> None:
    controller = controller_factory()
    controller.window.products_started = 1
    controller.edgehub.publish_monitoring_snapshot.return_value = False
    now = 100.0 + EDGEHUB_REPORTING_INTERVAL_SECONDS

    publish_edgehub_if_due(controller, now=now)

    assert controller.window.products_started == 1
    assert controller._last_edgehub_window_started_at == 100.0
