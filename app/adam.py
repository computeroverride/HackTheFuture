from pymodbus.client import ModbusTcpClient

from app.settings import Settings


class Adam6717Connection:
    def __init__(self, settings: Settings):
        self.settings = settings

        self.client = ModbusTcpClient(
            host=settings.adam_ip,
            port=settings.adam_port,
            timeout=3,
        )

    def connect(self) -> None:
        if not self.client.connect():
            raise ConnectionError(
                "Cannot connect to ADAM-6717 at "
                f"{self.settings.adam_ip}:{self.settings.adam_port}"
            )

        print(
            "Connected to ADAM-6717 at "
            f"{self.settings.adam_ip}:{self.settings.adam_port}"
        )

    def read_di2(self) -> bool:
        """Return True while DI2 button is pressed."""
        result = self.client.read_coils(
            address=self.settings.di2_address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read DI2: {result}")

        return bool(result.bits[0])

    def read_do0(self) -> bool:
        """Return current physical state of DO0."""
        result = self.client.read_coils(
            address=self.settings.do0_address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read DO0: {result}")

        return bool(result.bits[0])

    def write_do0(self, fan_on: bool) -> None:
        """True = relay/fan ON. False = relay/fan OFF."""
        result = self.client.write_coil(
            address=self.settings.do0_address,
            value=fan_on,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not write DO0: {result}")

    def close(self) -> None:
        self.client.close()