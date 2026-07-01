import time
from typing import Optional

from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import Settings


class ButtonFanService:
    """
    Handles only:
    DI2 button press -> toggle DO0 fan relay -> publish states.

    Important:
    This class does NOT contain an infinite while loop.
    main.py calls tick() repeatedly.
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

        self.fan_on = False
        self.previous_button_state = False
        self.button_press_count = 0
        self.last_event = "Gateway not started"

        self.last_toggle_time = 0.0
        self.last_publish_time = 0.0
        self.last_published_state = None

    def start(self) -> None:
        """
        Read the real ADAM state once before the central loop begins.

        This prevents an accidental toggle if DI2 is already being held
        when Python starts.
        """
        self.fan_on = self.adam.read_do0()
        self.previous_button_state = self.adam.read_di2()

        self.button_press_count = 0
        self.last_event = "Gateway started"

        print(f"Fan starts as: {'ON' if self.fan_on else 'OFF'}")
        print("Press DI2 once to toggle the fan.")

        self._publish_if_needed(
            now=time.monotonic(),
            button_pressed=self.previous_button_state,
            force=True,
        )

        self.started = True

    def tick(self, now: float) -> None:
        """
        Run one short control cycle only.

        main.py calls this repeatedly. Do not add while True here.
        """
        if not self.started:
            raise RuntimeError(
                "ButtonFanService.start() must run before tick()."
            )

        # Read DI2 once.
        button_pressed = self.adam.read_di2()

        # Detect only a fresh press: Released -> Pressed.
        new_press = (
            button_pressed
            and not self.previous_button_state
        )

        # Debounce prevents one press from toggling multiple times.
        if (
            new_press
            and now - self.last_toggle_time
            >= self.settings.debounce_seconds
        ):
            self.fan_on = not self.fan_on

            # Write the new fan state to physical DO0.
            self.adam.write_do0(self.fan_on)

            self.button_press_count += 1
            self.last_event = (
                f"DI2 pressed -> Fan "
                f"{'ON' if self.fan_on else 'OFF'}"
            )

            print(self.last_event)

            self.last_toggle_time = now

        # Read DO0 again so EdgeHub always receives the actual relay state.
        self.fan_on = self.adam.read_do0()

        self._publish_if_needed(
            now=now,
            button_pressed=button_pressed,
        )

        # Save this for the next cycle's Released -> Pressed detection.
        self.previous_button_state = button_pressed

    def _publish_if_needed(
        self,
        now: float,
        button_pressed: bool,
        force: bool = False,
    ) -> None:
        """
        Send only when a state changed, or when the heartbeat is due.
        """
        if self.edgehub is None:
            return

        current_state = (
            button_pressed,
            self.fan_on,
            self.button_press_count,
            self.last_event,
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
            success = self.edgehub.publish(
                button_pressed=button_pressed,
                fan_on=self.fan_on,
                button_press_count=self.button_press_count,
                last_event=self.last_event,
            )

            if success:
                self.last_published_state = current_state
                self.last_publish_time = now

                print(
                    "EdgeHub sent | "
                    f"Button={'Pressed' if button_pressed else 'Released'} | "
                    f"Fan={'ON' if self.fan_on else 'OFF'} | "
                    f"Count={self.button_press_count}"
                )
            else:
                print("EdgeHub send failed.")

        except Exception as error:
            # Physical ADAM control continues even if EdgeHub/Internet drops.
            print(f"EdgeHub publish error: {error}")