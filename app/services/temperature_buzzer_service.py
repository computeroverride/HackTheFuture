import time
from typing import Optional

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import Settings


class TemperatureBuzzerService:
    """
    Handles:

    AI2 voltage high -> DO1 buzzer ON
    AI2 voltage low  -> DO1 buzzer OFF

    Since the temperature sensor model is unknown,
    this service uses voltage thresholds instead of Celsius.
    """

    def __init__(
        self,
        settings: Settings,
        adam: Adam6717Connection,
        edgehub: Optional[EdgeHubPublisher] = None,
    ):
        self.settings = settings
        self.adam = adam
        self.edgehub = edgehub

        self.started = False

        self.ai2_voltage = 0.0
        self.buzzer_on = False
        self.temperature_alarm = False
        self.system_status = "UNKNOWN"
        self.last_event = "Temperature/buzzer service not started"

        self.last_publish_time = 0.0
        self.last_published_state = None

    def start(self) -> None:
        """Read the real ADAM state once before the loop starts."""

        self.ai2_voltage = self.adam.read_ai2_voltage()
        self.buzzer_on = self.adam.read_do1()

        self.temperature_alarm = self.buzzer_on
        self.system_status = (
            "WARNING" if self.temperature_alarm else "NORMAL"
        )

        self.last_event = (
            "Temperature/buzzer service started"
        )

        print(
            "AI2 starts as: "
            f"{self.ai2_voltage:.3f} V"
        )
        print(
            "Buzzer starts as: "
            f"{'ON' if self.buzzer_on else 'OFF'}"
        )

        self._publish_if_needed(
            now=time.monotonic(),
            force=True,
        )

        self.started = True

    def tick(self, now: float) -> None:
        """Run one short control cycle."""

        if not self.started:
            raise RuntimeError(
                "TemperatureBuzzerService.start() must run before tick()."
            )

        self.ai2_voltage = self.adam.read_ai2_voltage()

        # Turn buzzer ON when AI2 reaches the warm threshold.
        if (
            not self.buzzer_on
            and self.ai2_voltage >= self.settings.buzzer_on_voltage
        ):
            self.buzzer_on = True
            self.temperature_alarm = True
            self.system_status = "WARNING"

            self.adam.write_do1(True)

            self.last_event = (
                f"AI2 {self.ai2_voltage:.3f} V >= "
                f"{self.settings.buzzer_on_voltage:.3f} V "
                "-> Buzzer ON"
            )

            print(self.last_event)

        # Turn buzzer OFF only after AI2 falls below the lower threshold.
        elif (
            self.buzzer_on
            and self.ai2_voltage <= self.settings.buzzer_off_voltage
        ):
            self.buzzer_on = False
            self.temperature_alarm = False
            self.system_status = "NORMAL"

            self.adam.write_do1(False)

            self.last_event = (
                f"AI2 {self.ai2_voltage:.3f} V <= "
                f"{self.settings.buzzer_off_voltage:.3f} V "
                "-> Buzzer OFF"
            )

            print(self.last_event)

        # Read DO1 again so EdgeHub receives actual output state.
        self.buzzer_on = self.adam.read_do1()
        self.temperature_alarm = self.buzzer_on
        self.system_status = (
            "WARNING" if self.temperature_alarm else "NORMAL"
        )

        self._publish_if_needed(now=now)

    def _publish_if_needed(
        self,
        now: float,
        force: bool = False,
    ) -> None:
        """Send when state changed or heartbeat is due."""

        if self.edgehub is None:
            return

        current_state = (
            round(self.ai2_voltage, 3),
            self.buzzer_on,
            self.temperature_alarm,
            self.last_event,
            self.system_status,
        )

        state_changed = (
            current_state != self.last_published_state
        )

        heartbeat_due = (
            now - self.last_publish_time
            >= self.settings.publish_heartbeat_seconds
        )

        if not force and not state_changed and not heartbeat_due:
            return

        try:
            success = self.edgehub.publish_temperature_buzzer(
                ai2_voltage=self.ai2_voltage,
                buzzer_on=self.buzzer_on,
                temperature_alarm=self.temperature_alarm,
                last_event=self.last_event,
                system_status=self.system_status,
            )

            if success:
                self.last_published_state = current_state
                self.last_publish_time = now

                print(
                    "EdgeHub sent | "
                    f"AI2={self.ai2_voltage:.3f} V | "
                    f"Buzzer={'ON' if self.buzzer_on else 'OFF'} | "
                    f"Status={self.system_status}"
                )
            else:
                print("EdgeHub temperature/buzzer send failed.")

        except Exception as error:
            print(
                f"EdgeHub temperature/buzzer publish error: {error}"
            )