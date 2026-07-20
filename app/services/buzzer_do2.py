class BuzzerDO2:
    """
    Buzzer output.

    Function:
    - Controls buzzer on physical DO2.
    """

    def __init__(self, adam, settings):
        self.adam = adam
        self.settings = settings

    def start_buzzing(self) -> None:
        self.adam.write_do(
            self.settings.do2_address,
            True,
        )

    def stop_buzzing(self) -> None:
        self.adam.write_do(
            self.settings.do2_address,
            False,
        )

    def set_buzzer(self, buzzer_on: bool) -> None:
        self.adam.write_do(
            self.settings.do2_address,
            buzzer_on,
        )

    def is_buzzing(self) -> bool:
        return self.adam.read_do(
            self.settings.do2_address
        )