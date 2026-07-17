class CrashSensorDI0:
    """
    Good product pile crash sensor.

    Function:
    - Reads crash sensor on DI0.
    - Returns boolean.
    """

    def __init__(self, adam, settings):
        self.adam = adam
        self.settings = settings

    def is_crash_detected(self) -> bool:
        return self.adam.read_di(
            self.settings.di0_address
        )