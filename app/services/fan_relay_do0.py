class FanRelayDO0:
    """
    Fan relay output.

    Function:
    - Controls relay on DO0.
    - Used to turn fan ON/OFF.
    """

    def __init__(self, adam, settings):
        self.adam = adam
        self.settings = settings

    def turn_on(self) -> None:
        self.adam.write_do(
            self.settings.do0_address,
            True,
        )

    def turn_off(self) -> None:
        self.adam.write_do(
            self.settings.do0_address,
            False,
        )

    def set_fan(self, fan_on: bool) -> None:
        self.adam.write_do(
            self.settings.do0_address,
            fan_on,
        )

    def is_on(self) -> bool:
        return self.adam.read_do(
            self.settings.do0_address
        )