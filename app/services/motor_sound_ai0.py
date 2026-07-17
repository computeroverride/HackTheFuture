class MotorSoundAI0:
    """
    Motor sound sensor.

    Function:
    - Reads sound sensor on AI0.
    - Returns voltage value.
    """

    def __init__(self, adam, settings):
        self.adam = adam
        self.settings = settings

    def read_sound_value(self) -> float:
        return self.adam.read_ai_voltage(
            self.settings.ai0_address
        )

    def is_motor_loud(
        self,
        threshold_voltage=0.2,
    ) -> bool:
        voltage = self.read_sound_value()

        return voltage >= threshold_voltage