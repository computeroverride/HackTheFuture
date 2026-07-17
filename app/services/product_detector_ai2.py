class ProductDetectorAI2:
    """
    Conveyor belt product detector.

    Function:
    - Reads analog sensor on AI2.
    - Converts voltage into product detected boolean.
    """

    def __init__(
        self,
        adam,
        settings,
        detect_threshold_voltage=1.0,
    ):
        self.adam = adam
        self.settings = settings
        self.detect_threshold_voltage = detect_threshold_voltage

    def read_voltage(self) -> float:
        return self.adam.read_ai_voltage(
            self.settings.ai2_address
        )

    def is_product_detected(self) -> bool:
        voltage = self.read_voltage()

        return voltage >= self.detect_threshold_voltage