class CameraPhotocellAI4:
    """
    Camera station detector.

    Function:
    - Reads photocell on AI4.
    - Returns whether product is at camera station.
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

    def is_at_camera_station(self) -> bool:
        voltage = self.read_voltage()

        return voltage >= self.detect_threshold_voltage