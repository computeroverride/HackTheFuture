from __future__ import annotations

import time
from typing import Any

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import Settings
from app.services.buzzer_do2 import BuzzerDO2
from app.services.crash_sensor_di0 import CrashSensorDI0
from app.services.entry_button import EntryButton
from app.services.fan_relay_do0 import FanRelayDO0
from app.services.pill_inspector import PillInspector
from integrations.telegram_notifier import TelegramNotifier
from app.conveyor.constants import (
    EDGEHUB_REPORTING_INTERVAL_SECONDS,
    PHOTOCELL_ADDRESS,
    PHOTOCELL_REARM_SECONDS,
    PHOTOCELL_THRESHOLD_VOLTAGE,
    REJECT_CONFIRM_TIMEOUT_SECONDS,
)
from app.conveyor.helpers import (
    derive_sound_activated,
    format_product_id,
    read_ai_scan,
    refresh_current_outputs,
)
from app.conveyor.inspection import (
    inspect_product,
    notify_inspection_result,
    poll_telegram_feedback,
)
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


class ConveyorController:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.adam = Adam6717Connection(settings)
        self.edgehub: EdgeHubPublisher | None = None
        self.adam_connected = False
        self._last_adam_reconnect_attempt = 0.0

        self.entry_button = EntryButton(self.adam, settings)
        self.crash_sensor = CrashSensorDI0(self.adam, settings)
        self.fan_relay = FanRelayDO0(self.adam, settings)
        self.buzzer = BuzzerDO2(self.adam, settings)

        self.notifier = (
            TelegramNotifier(settings)
            if settings.telegram_enabled
            else None
        )

        self.inspector: PillInspector | None = None
        try:
            self.inspector = PillInspector(
                camera_index=settings.camera_index,
                burst_count=settings.camera_burst_count,
                burst_delay_seconds=settings.camera_burst_gap_seconds,
            )
        except Exception as error:
            print(
                "Vision inspection is unavailable. "
                "Inspections will fail safely."
            )
            print(f"Inspection setup error: {error}")

        self.process_state = "IDLE"
        self.current_product_id = ""
        self.current_result: dict[str, Any] | None = None
        self.product_started_at: float | None = None
        self.reject_started_at: float | None = None
        self.reject_sound_previous = False

        self.last_product_event = "System started"
        self.last_completed_product_id = ""

        self.product_at_camera_now = False
        self.completion_sensor_active_now = False
        self.reject_fan_on = False
        self.buzzer_on = False

        self.classification_status = "PENDING"
        self.ml_prediction = ""
        self.ml_confidence_percent = 0.0

        self.feedback_product_id = ""
        self.feedback_status = "Pending"
        self.actual_class = ""
        self.feedback_received = False
        self.ml_prediction_correct = False

        self.alarm_active = False
        self.last_alarm_message = ""
        self.last_reject_confirmed = False

        self.inspection_count_total = 0
        self.good_count_total = 0
        self.fail_defect_count_total = 0
        self.fail_different_count_total = 0
        self.reject_confirmed_total = 0
        self.reject_timeout_total = 0
        self.feedback_count_total = 0
        self.ml_correction_count_total = 0

        self.last_cycle_time_seconds = 0.0
        self._cycle_time_total_seconds = 0.0
        self._finished_cycle_count = 0

        self.window = ReportingWindow()
        self._last_edgehub_window_started_at = time.monotonic()
        self._last_feedback_poll = time.monotonic()
        self._last_status_print = time.monotonic()

    def connect(self) -> None:
        try:
            self.adam.connect()
            self.adam_connected = True
        except Exception as error:
            print(
                "ADAM-6717 is unavailable. "
                "Starting with hardware monitoring offline."
            )
            print(f"ADAM connection error: {error}")
            self.adam_connected = False

        if self.settings.edgehub_enabled:
            try:
                self.edgehub = EdgeHubPublisher(self.settings)
                self.edgehub.connect_and_upload_tags()
                self._last_edgehub_window_started_at = time.monotonic()
            except Exception as error:
                print(
                    "EdgeHub is unavailable. "
                    "The conveyor workflow will continue locally."
                )
                print(f"EdgeHub connection error: {error}")
                self.edgehub = None

    def _attempt_adam_reconnect(self, now: float) -> None:
        if now - self._last_adam_reconnect_attempt < 10.0:
            return

        self._last_adam_reconnect_attempt = now

        try:
            try:
                self.adam.close()
            except Exception:
                pass

            self.adam.connect()
            self.adam_connected = True
            print("ADAM reconnected.")
        except Exception as error:
            self.adam_connected = False
            print(f"ADAM reconnect failed: {error}")

    def _handle_adam_failure(self, error: Exception) -> None:
        if self.adam_connected:
            print(
                "ADAM connection lost during operation: "
                f"{error}"
            )
        self.adam_connected = False

    @property
    def average_cycle_time_seconds(self) -> float:
        if self._finished_cycle_count <= 0:
            return 0.0
        return self._cycle_time_total_seconds / self._finished_cycle_count

    def run(self) -> None:
        self.connect()

        print()
        print("CMIO product-monitoring controller is running.")
        print(
            "EdgeHub sends one consolidated data snapshot every "
            "60 seconds."
        )
        print("No images or raw sensor voltages are sent to EdgeHub.")
        print("Press Ctrl+C to stop.")
        print()

        photocell_armed = False
        photocell_clear_started_at: float | None = None

        if self.adam_connected:
            try:
                readings = read_ai_scan(self.adam)
                initial_photocell_voltage = readings[PHOTOCELL_ADDRESS]
                photocell_armed = (
                    initial_photocell_voltage >= PHOTOCELL_THRESHOLD_VOLTAGE
                )
            except Exception as error:
                self._handle_adam_failure(error)

        try:
            while True:
                now = time.monotonic()
                poll_telegram_feedback(self, now)

                if not self.adam_connected:
                    self._attempt_adam_reconnect(now)

                if self.adam_connected:
                    try:
                        new_product_id = self.entry_button.get_product_id_if_pressed()
                    except Exception as error:
                        self._handle_adam_failure(error)
                        new_product_id = None

                    if new_product_id is not None:
                        if self.process_state != "IDLE":
                            print(
                                "Button press ignored because "
                                f"{self.current_product_id} is still in progress."
                            )
                        else:
                            start_product(self, new_product_id, now)

                    try:
                        readings = read_ai_scan(self.adam)
                        photocell_voltage = readings[PHOTOCELL_ADDRESS]
                        self.product_at_camera_now = (
                            photocell_voltage < PHOTOCELL_THRESHOLD_VOLTAGE
                        )
                        sound_activated = derive_sound_activated(
                            self.settings,
                            self.adam,
                            readings,
                        )
                        self.completion_sensor_active_now = bool(
                            self.crash_sensor.is_crash_detected()
                        )
                        refresh_current_outputs(self)
                    except Exception as error:
                        self._handle_adam_failure(error)
                        sound_activated = False
                        self.product_at_camera_now = False
                        self.completion_sensor_active_now = False

                    if not self.product_at_camera_now:
                        if not photocell_armed:
                            if photocell_clear_started_at is None:
                                photocell_clear_started_at = now
                            elif now - photocell_clear_started_at >= PHOTOCELL_REARM_SECONDS:
                                photocell_armed = True
                                photocell_clear_started_at = None
                    else:
                        photocell_clear_started_at = None

                    if (
                        self.process_state == "WAITING_FOR_PHOTOCELL"
                        and self.product_at_camera_now
                        and photocell_armed
                    ):
                        photocell_armed = False
                        self.window.photocell_triggered = True
                        self.process_state = "INSPECTING"
                        self.last_product_event = (
                            f"{self.current_product_id} detected at camera"
                        )

                        print()
                        print(
                            "Photocell detected product: "
                            f"{self.current_product_id}"
                        )
                        print("Capturing and running ML inspection...")

                        result = inspect_product(self, self.current_product_id)
                        record_inspection(self, result)

                        print(
                            "Inspection result -> "
                            f"label={self.ml_prediction}, "
                            f"confidence={self.ml_confidence_percent:.1f}%"
                        )

                        notify_inspection_result(
                            self,
                            self.current_product_id,
                            result,
                        )

                        if result.get("is_pass"):
                            set_fan(self, False)
                            set_buzzer(self, False)
                            self.process_state = "GOOD_AWAITING_COMPLETION"
                            self.last_product_event = (
                                f"{self.current_product_id} passed; "
                                "waiting for completion sensor"
                            )
                        else:
                            set_buzzer(self, False)
                            set_fan(self, True)
                            self.process_state = "REJECTING"
                            self.reject_started_at = now
                            self.reject_sound_previous = sound_activated
                            self.last_reject_confirmed = False
                            self.last_product_event = (
                                f"{self.current_product_id} rejected; "
                                "waiting for reject-bin impact"
                            )

                    elif (
                        self.process_state == "GOOD_AWAITING_COMPLETION"
                        and self.completion_sensor_active_now
                    ):
                        self.window.completion_detected = True
                        self.window.products_completed += 1
                        set_fan(self, False)
                        set_buzzer(self, False)

                        product_id = self.current_product_id
                        print(
                            "Good completion confirmed: "
                            f"{product_id}"
                        )

                        if self.notifier is not None:
                            self.notifier.send(
                                "✅ Good completion confirmed: "
                                f"{product_id}"
                            )

                        finish_product(
                            self,
                            now,
                            f"Good completion confirmed for {product_id}",
                        )

                    elif self.process_state == "REJECTING":
                        impact_rising_edge = (
                            sound_activated
                            and not self.reject_sound_previous
                        )
                        self.reject_sound_previous = sound_activated

                        if impact_rising_edge:
                            self.window.reject_impact_detected = True
                            self.window.products_rejected += 1
                            self.reject_confirmed_total += 1
                            self.last_reject_confirmed = True
                            set_fan(self, False)
                            set_buzzer(self, False)

                            product_id = self.current_product_id
                            print(
                                "Reject-bin impact confirmed: "
                                f"{product_id}"
                            )

                            if self.notifier is not None:
                                self.notifier.send(
                                    "🗑️ Rejection confirmed: "
                                    f"{product_id}"
                                )

                            finish_product(
                                self,
                                now,
                                f"Rejection confirmed for {product_id}",
                            )

                        elif (
                            self.reject_started_at is not None
                            and now - self.reject_started_at
                            >= REJECT_CONFIRM_TIMEOUT_SECONDS
                        ):
                            self.window.reject_timeouts += 1
                            self.reject_timeout_total += 1
                            self.last_reject_confirmed = False
                            self.alarm_active = True
                            self.last_alarm_message = (
                                "Reject-bin impact was not detected for "
                                f"{self.current_product_id}"
                            )

                            set_fan(self, False)
                            set_buzzer(self, True)

                            product_id = self.current_product_id
                            print(
                                "Reject confirmation timed out: "
                                f"{product_id}"
                            )

                            if self.notifier is not None:
                                self.notifier.alarm(self.last_alarm_message)

                            finish_product(
                                self,
                                now,
                                f"Reject confirmation failed for {product_id}",
                            )

                publish_edgehub_if_due(self, now)

                if now - self._last_status_print >= 10.0:
                    print(
                        "Status -> "
                        f"state={self.process_state}, "
                        f"product={self.current_product_id or 'none'}, "
                        f"camera_sensor={self.product_at_camera_now}, "
                        f"completion_sensor={self.completion_sensor_active_now}, "
                        f"fan={self.reject_fan_on}, "
                        f"alarm={self.alarm_active}"
                    )
                    self._last_status_print = now

                time.sleep(
                    max(float(self.settings.poll_interval_seconds), 0.10)
                )

        except KeyboardInterrupt:
            print()
            print("Stopped by user.")

        finally:
            try:
                self.fan_relay.turn_off()
            except Exception:
                pass

            try:
                self.buzzer.stop_buzzing()
            except Exception:
                pass

            try:
                close_inspector = getattr(self.inspector, "close", None)
                if callable(close_inspector):
                    close_inspector()
            except Exception:
                pass

            if self.edgehub is not None:
                try:
                    self.edgehub.disconnect()
                except Exception:
                    pass

            try:
                self.adam.close()
            except Exception:
                pass
