from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import load_settings
from app.services.buzzer_do2 import BuzzerDO2
from app.services.crash_sensor_di0 import CrashSensorDI0
from app.services.entry_button import EntryButton
from app.services.fan_relay_do0 import FanRelayDO0
from app.services.motor_sound_ai0 import MotorSoundAI0
from app.services.pill_inspector import PillInspector
from integrations.telegram_notifier import TelegramNotifier


# =========================================================
# Proven photocell configuration from test_photocell_camera.py
# =========================================================

# Your ADAM only returns the changing AI4 value at address 38
# when all of these addresses are read in this sequence.
AI_SCAN_ADDRESSES = [
    30,
    32,
    34,
    36,
    38,
    40,
    42,
]

PHOTOCELL_ADDRESS = 38
PHOTOCELL_THRESHOLD_VOLTAGE = 0.1000
PHOTOCELL_REARM_SECONDS = 2.0

# Time for a rejected product to travel from the camera station
# to the fan/reject point. Adjust this after timing the conveyor.
REJECT_TRAVEL_SECONDS = 1.0

# How long the fan may remain active while waiting for the sound
# sensor to confirm that the product entered the reject bin.
REJECT_CONFIRM_TIMEOUT_SECONDS = 2.0

# Sound-sensor threshold used to confirm reject-bin impact.
REJECT_SOUND_THRESHOLD_VOLTAGE = 0.2

# Labels accepted by TelegramNotifier.send_inspection_result().
TELEGRAM_FEEDBACK_LABELS = {
    "good",
    "fail_different",
    "fail_defect",
}


class ConveyorController:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.adam = Adam6717Connection(settings)
        self.edgehub: EdgeHubPublisher | None = None
        self.adam_connected = False
        self._last_adam_connection_state: bool | None = None
        self._last_status_text = ""
        self._last_status_time = 0.0
        self._last_adam_reconnect_attempt = 0.0

        self.entry_button = EntryButton(self.adam, settings)
        self.crash_sensor = CrashSensorDI0(self.adam, settings)
        self.fan_relay = FanRelayDO0(self.adam, settings)
        self.motor_sound = MotorSoundAI0(self.adam, settings)
        self.buzzer = BuzzerDO2(self.adam, settings)

        self.notifier = (
            TelegramNotifier(settings)
            if settings.telegram_enabled
            else None
        )

        self.inspector: PillInspector | None = None

        try:
            # PillInspector is expected to:
            # 1. capture the configured burst of camera frames;
            # 2. choose/save the sharpest frame;
            # 3. run the trained AI/ML model;
            # 4. return is_pass, final_label, confidence and saved_image.
            self.inspector = PillInspector(
                camera_index=settings.camera_index,
                burst_count=settings.camera_burst_count,
                burst_delay_seconds=(
                    settings.camera_burst_gap_seconds
                ),
            )
        except Exception as error:
            print(
                "Vision inspection is unavailable. "
                "The controller will fail inspections safely."
            )
            print(f"Inspection setup error: {error}")

    # =====================================================
    # Connections
    # =====================================================

    def connect(self) -> None:
        try:
            self.adam.connect()
            self.adam_connected = True
        except Exception as error:
            print(
                "ADAM-6717 is unavailable. "
                "Starting in offline/demo mode."
            )
            print(f"ADAM connection error: {error}")
            self.adam_connected = False

        if self.settings.edgehub_enabled:
            try:
                self.edgehub = EdgeHubPublisher(
                    self.settings
                )
                self.edgehub.connect_and_upload_tags()
            except Exception as error:
                print(
                    "EdgeHub is unavailable. "
                    "ADAM control will still run."
                )
                print(f"EdgeHub connection error: {error}")
                self.edgehub = None

        self._last_adam_connection_state = self.adam_connected

    # =====================================================
    # Photocell
    # =====================================================

    def _read_photocell_voltage(self) -> float:
        """
        Read every AI address in the exact sequence proven by the
        working photocell/camera test, then return address 38.
        """
        readings: dict[int, float] = {}

        for address in AI_SCAN_ADDRESSES:
            readings[address] = self.adam.read_ai_voltage(
                address
            )

        if PHOTOCELL_ADDRESS not in readings:
            raise RuntimeError(
                f"Photocell address {PHOTOCELL_ADDRESS} "
                "was not returned by the AI scan."
            )

        return readings[PHOTOCELL_ADDRESS]

    # =====================================================
    # Inspection + Telegram
    # =====================================================

    @staticmethod
    def _normalise_label(label: object) -> str:
        value = str(label or "unknown").strip().lower()

        aliases = {
            "pass": "good",
            "passed": "good",
            "different": "fail_different",
            "defect": "fail_defect",
            "defective": "fail_defect",
        }

        return aliases.get(value, value)

    @staticmethod
    def _extract_product_number(
        product_id: object,
    ) -> int | None:
        """
        Convert IDs such as 1, P001 or PRODUCT-001 to integer 1.
        TelegramNotifier uses an integer to format P001.
        """
        if isinstance(product_id, int):
            return product_id

        matches = re.findall(r"\d+", str(product_id))

        if not matches:
            return None

        return int(matches[-1])

    def _inspect_product(
        self,
        product_id: str,
    ) -> dict[str, Any]:
        if self.inspector is None:
            return {
                "is_pass": False,
                "final_label": "inspection_unavailable",
                "confidence": 0.0,
                "saved_image": None,
            }

        try:
            result = self.inspector.inspect(product_id)

            if not isinstance(result, dict):
                raise TypeError(
                    "PillInspector.inspect() must return a dict."
                )

            label = self._normalise_label(
                result.get(
                    "final_label",
                    result.get("label", "unknown"),
                )
            )

            confidence = float(
                result.get("confidence", 0.0)
            )

            saved_image = result.get(
                "saved_image",
                result.get("image_path"),
            )

            # Prefer the inspector's is_pass value when present,
            # but make "good" pass automatically as a fallback.
            is_pass = bool(
                result.get(
                    "is_pass",
                    label == "good",
                )
            )

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

    def _notify_inspection_result(
        self,
        product_id: str,
        result: dict[str, Any],
    ) -> None:
        """Send every captured inspection image with class-feedback buttons.

        The feedback buttons represent the ACTUAL class, so they should still
        be shown when the ML prediction is uncertain or uses an unexpected
        label.
        """
        if self.notifier is None:
            print("Telegram notifier is disabled.")
            return

        label = self._normalise_label(
            result.get("final_label", "unknown")
        )
        confidence = float(result.get("confidence", 0.0))
        saved_image = result.get(
            "saved_image",
            result.get("image_path"),
        )
        product_number = self._extract_product_number(product_id)

        print(
            "Telegram inspection payload -> "
            f"product_id={product_id!r}, "
            f"product_number={product_number!r}, "
            f"label={label!r}, "
            f"saved_image={saved_image!r}"
        )

        if not saved_image:
            print(
                "Feedback buttons not sent: PillInspector returned no "
                "saved_image/image_path."
            )
            self.notifier.send(
                f"Inspection completed for {product_id}\n"
                f"ML prediction: {label}\n"
                f"Confidence: {confidence}\n"
                "No inspection image was returned."
            )
            return

        image_path = Path(saved_image)
        if not image_path.exists():
            print(
                "Feedback buttons not sent: inspection image does not "
                f"exist at {image_path}."
            )
            return

        if product_number is None:
            print(
                "Feedback buttons not sent: product ID contains no number: "
                f"{product_id!r}."
            )
            return

        try:
       
            self.notifier.send_inspection_result(
                product_id=product_number,
                predicted_label=label,
                confidence=confidence,
                image_path=image_path,
            )
            print("Telegram inspection photo sent with feedback buttons.")
        except Exception as error:
            print(
                "Telegram inspection result failed before buttons could "
                f"be attached: {error}"
            )

    # =====================================================
    # State machine
    # =====================================================

    def run(self) -> None:
        self.connect()

        print()
        print("CMIO conveyor controller is running.")
        print(
            f"Photocell AI address: "
            f"{PHOTOCELL_ADDRESS}"
        )
        print(
            f"Photocell trigger: below "
            f"{PHOTOCELL_THRESHOLD_VOLTAGE:.4f} V"
        )
        print(
            f"AI scan sequence: {AI_SCAN_ADDRESSES}"
        )

        if self.adam_connected:
            print("ADAM control is active.")
        else:
            print(
                "ADAM control is disabled; "
                "running in offline mode."
            )

        print("Press Ctrl+C to stop.")
        print()

        state = "idle"
        current_product_id: str | None = None
        current_result: dict[str, Any] | None = None

        last_heartbeat = time.monotonic()
        last_feedback_poll = time.monotonic()

        photocell_armed = False
        photocell_clear_started_at: float | None = None
        last_photocell_voltage: float | None = None

        reject_move_started_at: float | None = None
        reject_fan_started_at: float | None = None

        if self.adam_connected:
            try:
                initial_voltage = (
                    self._read_photocell_voltage()
                )
                last_photocell_voltage = initial_voltage
                photocell_armed = (
                    initial_voltage
                    >= PHOTOCELL_THRESHOLD_VOLTAGE
                )

                if not photocell_armed:
                    print(
                        "Photocell is covered at startup. "
                        "Uncover it to arm the station."
                    )
            except Exception as error:
                print(
                    "Initial photocell read failed: "
                    f"{error}"
                )

        try:
            while True:
                now = time.monotonic()

                # Poll Telegram so inline feedback buttons work.
                if (
                    self.notifier is not None
                    and now - last_feedback_poll >= 1.0
                ):
                    self.notifier.get_feedback_messages()
                    last_feedback_poll = now

                if not self.adam_connected:
                    self._attempt_adam_reconnect(now)

                if self.adam_connected:
                    # -----------------------------------------
                    # Button pressed -> generate product ID
                    # -----------------------------------------
                    try:
                        new_product_id = (
                            self.entry_button
                            .get_product_id_if_pressed()
                        )
                    except Exception as error:
                        self._handle_adam_failure(error)
                        new_product_id = None

                    if new_product_id is not None:
                        if state != "idle":
                            print(
                                "Button press ignored because "
                                f"{current_product_id} is still "
                                "being processed."
                            )
                        else:
                            current_product_id = str(
                                new_product_id
                            )
                            current_result = None
                            reject_move_started_at = None
                            reject_fan_started_at = None

                            self.fan_relay.turn_off()
                            self.buzzer.stop_buzzing()

                            state = "waiting_for_detection"

                            print()
                            print(
                                "Button pressed -> product "
                                f"created: {current_product_id}"
                            )
                            print(
                                "Conveyor started/continuing. "
                                "Waiting for IR photocell."
                            )

                            if self.notifier is not None:
                                self.notifier.send(
                                    "🆔 New product created: "
                                    f"{current_product_id}"
                                )

                    # -----------------------------------------
                    # Read photocell using proven full AI scan
                    # -----------------------------------------
                    try:
                        photocell_voltage = (
                            self._read_photocell_voltage()
                        )
                        last_photocell_voltage = (
                            photocell_voltage
                        )
                    except Exception as error:
                        self._handle_adam_failure(error)
                        photocell_voltage = last_photocell_voltage or 0.0
                        product_at_camera = False
                        continue
                    product_at_camera = (
                        photocell_voltage
                        < PHOTOCELL_THRESHOLD_VOLTAGE
                    )

                    # Rearm only after the photocell has remained
                    # clear for the configured cooldown.
                    if not product_at_camera:
                        if not photocell_armed:
                            if (
                                photocell_clear_started_at
                                is None
                            ):
                                photocell_clear_started_at = now

                            if (
                                now
                                - photocell_clear_started_at
                                >= PHOTOCELL_REARM_SECONDS
                            ):
                                photocell_armed = True
                                photocell_clear_started_at = None
                                print(
                                    "Photocell armed for the "
                                    "next detection."
                                )
                    else:
                        photocell_clear_started_at = None

                    # -----------------------------------------
                    # IR detects product -> camera + AI/ML
                    # -----------------------------------------
                    if (
                        state == "waiting_for_detection"
                        and product_at_camera
                        and photocell_armed
                    ):
                        # Disarm immediately so one product can
                        # trigger only one inspection.
                        photocell_armed = False

                        print()
                        print(
                            "IR detected product at camera "
                            f"station: {current_product_id}"
                        )
                        print(
                            "Capturing camera burst and "
                            "running AI/ML inspection..."
                        )

                        current_result = (
                            self._inspect_product(
                                current_product_id
                                or "unknown"
                            )
                        )

                        label = current_result.get(
                            "final_label",
                            "unknown",
                        )
                        confidence = float(
                            current_result.get(
                                "confidence",
                                0.0,
                            )
                        )

                        print(
                            "Inspection result -> "
                            f"label={label}, "
                            f"confidence={confidence:.4f}"
                        )

                        self._notify_inspection_result(
                            current_product_id or "unknown",
                            current_result,
                        )

                        if current_result.get("is_pass"):
                            # GOOD: fan stays off and conveyor
                            # continues to the crash sensor.
                            self.fan_relay.turn_off()
                            self.buzzer.stop_buzzing()
                            state = "awaiting_good_completion"

                            print(
                                f"GOOD: {current_product_id}. "
                                "Fan remains OFF; waiting for "
                                "completion crash sensor."
                            )
                        else:
                            # BAD: allow the product to travel to
                            # the reject point before activating fan.
                            self.fan_relay.turn_off()
                            self.buzzer.stop_buzzing()
                            reject_move_started_at = now
                            state = "moving_to_reject"

                            print(
                                f"BAD: {current_product_id}. "
                                "Moving to reject point."
                            )

                    # -----------------------------------------
                    # GOOD path: crash sensor completes journey
                    # -----------------------------------------
                    elif state == "awaiting_good_completion":
                        try:
                            crash_detected = (
                                self.crash_sensor.is_crash_detected()
                            )
                        except Exception as error:
                            self._handle_adam_failure(error)
                            crash_detected = False

                        if crash_detected:
                            self.fan_relay.turn_off()
                            self.buzzer.stop_buzzing()

                            print(
                                "Good completion confirmed: "
                                f"{current_product_id}"
                            )

                            if self.notifier is not None:
                                self.notifier.send(
                                    "✅ Good completion confirmed: "
                                    f"{current_product_id}"
                                )

                            state = "idle"
                            current_product_id = None
                            current_result = None

                    # -----------------------------------------
                    # BAD path: travel to reject point
                    # -----------------------------------------
                    elif state == "moving_to_reject":
                        if (
                            reject_move_started_at is not None
                            and now - reject_move_started_at
                            >= REJECT_TRAVEL_SECONDS
                        ):
                            self.fan_relay.turn_on()

                            # Keep buzzer OFF because the sound
                            # sensor must listen for bin impact.
                            self.buzzer.stop_buzzing()

                            reject_fan_started_at = now
                            state = "reject_fan_active"

                            print(
                                "Reject point reached -> "
                                "fan relay ON."
                            )

                    # -----------------------------------------
                    # BAD path: sound sensor confirms impact
                    # -----------------------------------------
                    elif state == "reject_fan_active":
                        try:
                            reject_confirmed = (
                                self.motor_sound.is_motor_loud(
                                    threshold_voltage=(
                                        REJECT_SOUND_THRESHOLD_VOLTAGE
                                    )
                                )
                            )
                        except Exception as error:
                            self._handle_adam_failure(error)
                            reject_confirmed = False

                        if reject_confirmed:
                            self.fan_relay.turn_off()
                            self.buzzer.stop_buzzing()

                            print(
                                "Reject-bin impact confirmed: "
                                f"{current_product_id}"
                            )

                            if self.notifier is not None:
                                self.notifier.send(
                                    "🗑️ Rejection confirmed: "
                                    f"{current_product_id}"
                                )

                            state = "idle"
                            current_product_id = None
                            current_result = None
                            reject_move_started_at = None
                            reject_fan_started_at = None

                        elif (
                            reject_fan_started_at is not None
                            and now - reject_fan_started_at
                            >= REJECT_CONFIRM_TIMEOUT_SECONDS
                        ):
                            self.fan_relay.turn_off()
                            self.buzzer.stop_buzzing()

                            print(
                                "Reject confirmation timed out: "
                                f"{current_product_id}"
                            )

                            if self.notifier is not None:
                                self.notifier.alarm(
                                    "No reject-bin impact was "
                                    "detected for "
                                    f"{current_product_id}."
                                )

                            state = "idle"
                            current_product_id = None
                            current_result = None
                            reject_move_started_at = None
                            reject_fan_started_at = None

                if now - last_heartbeat >= 10.0:
                    photocell_text = (
                        f"{last_photocell_voltage:.4f} V"
                        if last_photocell_voltage is not None
                        else "unavailable"
                    )

                    status_text = (
                        f"State: {state} | "
                        f"Product: {current_product_id or 'none'} | "
                        f"AI4: {photocell_text} | "
                        f"Armed: {photocell_armed}"
                    )

                    if (
                        status_text != self._last_status_text
                        or now - self._last_status_time >= 60.0
                    ):
                        print(status_text)
                        self._last_status_text = status_text
                        self._last_status_time = now

                    last_heartbeat = now

                # The working sensor test uses 0.10 s. Do not
                # scan the seven AI addresses faster than that.
                time.sleep(
                    max(
                        self.settings.poll_interval_seconds,
                        0.10,
                    )
                )

        except KeyboardInterrupt:
            print()
            print("Stopped by user.")

        finally:
            # Always leave outputs in a safe state.
            try:
                self.fan_relay.turn_off()
            except Exception:
                pass

            try:
                self.buzzer.stop_buzzing()
            except Exception:
                pass

    def _handle_adam_failure(
        self,
        error: Exception,
    ) -> None:
        if self.adam_connected:
            print(
                "ADAM connection lost during operation: "
                f"{error}"
            )

        self.adam_connected = False
        self._attempt_adam_reconnect(
            time.monotonic()
        )

    def _attempt_adam_reconnect(
        self,
        now: float,
        ) -> bool:
            if now - self._last_adam_reconnect_attempt < 10.0:
                return False

            self._last_adam_reconnect_attempt = now
            try:
                self.adam.reconnect()
                self.adam_connected = True
                print("ADAM reconnected.")
                return True
            except Exception as error:
                if self.adam_connected:
                    print(
                        "Failed to reconnect ADAM: "
                        f"{error}"
                    )
                self.adam_connected = False
                return False

            try:
                self.adam.write_do2(False)
            except Exception:
                pass

            # Release the camera if PillInspector exposes close().
            try:
                close_inspector = getattr(
                    self.inspector,
                    "close",
                    None,
                )

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


def main() -> None:
    settings = load_settings()
    controller = ConveyorController(settings)
    controller.run()


if __name__ == "__main__":
    main()