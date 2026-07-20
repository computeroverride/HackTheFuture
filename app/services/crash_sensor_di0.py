class CrashSensorDI0:
   
    def __init__(self, adam, settings):
        self.adam = adam
        self.settings = settings

    def is_crash_detected(self) -> bool:
        return self.adam.read_di(
            self.settings.di0_address
        )