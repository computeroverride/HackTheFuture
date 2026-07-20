import math
import struct

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
                f"Could not connect to ADAM-6717 at "
                f"{self.settings.adam_ip}:{self.settings.adam_port}"
            )

        print(
            f"Connected to ADAM-6717 at "
            f"{self.settings.adam_ip}:{self.settings.adam_port}"
        )

    # ========================================================
    # GENERIC DIGITAL INPUT
    # ========================================================

    def read_di(self, address: int) -> bool:
        result = self.client.read_coils(
            address=address,
            address=address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(
                f"Could not read DI address {address}: {result}"
            )

        return bool(result.bits[0])

    # ========================================================
    # GENERIC DIGITAL OUTPUT
    # ========================================================

    def read_do(self, address: int) -> bool:
        result = self.client.read_coils(
            address=address,
            address=address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(
                f"Could not read DO address {address}: {result}"
            )

        return bool(result.bits[0])

    def write_do(self, address: int, value: bool) -> None:
        result = self.client.write_coil(
            address=address,
            value=value,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(
                f"Could not write DO address {address}: {result}"
            )

    # ========================================================
    # GENERIC ANALOG INPUT
    # ========================================================

    def read_ai_voltage(self, address: int) -> float:
        result = self.client.read_holding_registers(
            address=address,
            count=2,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(
                f"Could not read AI address {address}: {result}"
            )

        return self._decode_cdab_float(result.registers)

    def _decode_cdab_float(self, registers) -> float:
        raw_bytes = struct.pack(
            ">HH",
            registers[1],
            registers[0],
        )

        value = struct.unpack(">f", raw_bytes)[0]

        if not math.isfinite(value):
            return 0.0

        return value

    # ========================================================
    # OLD WRAPPERS
    # Keep these so older code still works.
    # ========================================================

    def read_di2(self) -> bool:
        return self.read_di(self.settings.di2_address)

    def read_do0(self) -> bool:
        return self.read_do(self.settings.do0_address)

    def write_do0(self, fan_on: bool) -> None:
        self.write_do(self.settings.do0_address, fan_on)

    def read_do1(self) -> bool:
        return self.read_do(self.settings.do1_address)

    def write_do1(self, buzzer_on: bool) -> None:
        self.write_do(self.settings.do1_address, buzzer_on)

    def read_ai2_voltage(self) -> float:
        return self.read_ai_voltage(self.settings.ai2_address)

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        self.client.close()