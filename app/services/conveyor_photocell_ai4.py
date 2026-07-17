class ConveyorPhotocellAI4:
    """
    Conveyor belt product detector.

    Function:
    - Reads photocell on AI4.
    - Returns whether a product is detected on the conveyor.
    """

    def __init__(
        self,
        adam,
        settings,
        detect_threshold_voltage=0.3,
    ):
        self.adam = adam
        self.settings = settings
        self.detect_threshold_voltage = detect_threshold_voltage

    def read_voltage(self) -> float:
        return self.adam.read_ai_voltage(
            self.settings.ai4_address
        )

    def is_product_detected(self) -> bool:
        voltage = self.read_voltage()

        return voltage >= self.detect_threshold_voltage