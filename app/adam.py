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

    # ---------- low-level helpers ----------
    def read_di(self, address: int) -> bool:
        result = self.client.read_coils(
            address=address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read DI/coil {address}: {result}")

        return bool(result.bits[0])

    def read_do(self, address: int) -> bool:
        result = self.client.read_coils(
            address=address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read DO/coil {address}: {result}")

        return bool(result.bits[0])

    def write_do(self, address: int, value: bool) -> None:
        result = self.client.write_coil(
            address=address,
            value=value,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not write DO/coil {address}: {result}")

    # ---------- named inputs ----------
    def read_camera_sensor(self) -> bool:
        return self.read_di(self.settings.di_camera_sensor_address)

    def read_end_sensor(self) -> bool:
        return self.read_di(self.settings.di_end_sensor_address)

    def read_button(self) -> bool:
        return self.read_di(self.settings.di_button_address)

    # ---------- named outputs ----------
    def read_conveyor(self) -> bool:
        return self.read_do(self.settings.do_conveyor_address)

    def write_conveyor(self, on: bool) -> None:
        self.write_do(self.settings.do_conveyor_address, on)

    def write_servo_trigger(self, on: bool) -> None:
        self.write_do(self.settings.do_servo_trigger_address, on)

    def write_buzzer(self, on: bool) -> None:
        self.write_do(self.settings.do_buzzer_address, on)

    def write_fan(self, on: bool) -> None:
        self.write_do(self.settings.do_fan_address, on)

    # ---------- old aliases ----------
    def read_di2(self) -> bool:
        return self.read_button()

    def read_do0(self) -> bool:
        return self.read_conveyor()

    def write_do0(self, value: bool) -> None:
        self.write_conveyor(value)

    def close(self) -> None:
        self.client.close()