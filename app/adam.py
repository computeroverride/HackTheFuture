import math
import struct

from pymodbus.client import ModbusTcpClient

from app.settings import Settings


class Adam6717Connection:
    """
    Handles all Modbus TCP communication with the ADAM-6717.

    Current mappings:
    DI2 = button
    DO0 = fan relay
    AI2 = temperature sensor voltage
    DO1 = buzzer
    """

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

    # ========================================================
    # DIGITAL INPUTS
    # ========================================================
    def read_di2(self) -> bool:
        """
        Return True while DI2 button is pressed.

        Your ADAM exposes DI through the 0X bit map,
        so read_coils is used.
        """

        result = self.client.read_coils(
            address=self.settings.di2_address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read DI2: {result}")

        return bool(result.bits[0])

    # ========================================================
    # DIGITAL OUTPUTS
    # ========================================================
    def read_do0(self) -> bool:
        """Return current physical state of DO0 fan relay."""

        result = self.client.read_coils(
            address=self.settings.do0_address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read DO0: {result}")

        return bool(result.bits[0])

    def write_do0(self, fan_on: bool) -> None:
        """True = fan relay ON. False = fan relay OFF."""

        result = self.client.write_coil(
            address=self.settings.do0_address,
            value=fan_on,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not write DO0: {result}")

    def read_do1(self) -> bool:
        """Return current physical state of DO1 buzzer."""

        result = self.client.read_coils(
            address=self.settings.do1_address,
            count=1,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read DO1: {result}")

        return bool(result.bits[0])

    def write_do1(self, buzzer_on: bool) -> None:
        """True = buzzer ON. False = buzzer OFF."""

        result = self.client.write_coil(
            address=self.settings.do1_address,
            value=buzzer_on,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not write DO1: {result}")

    # ========================================================
    # ANALOG INPUTS
    # ========================================================
    def _decode_cdab_float(
        self,
        registers: list[int],
    ) -> float:
        """
        Decode ADAM analog input float.

        Your diagnostic confirmed:
        AI2 offset 34
        register order CDAB

        Example:
        [14680, 16420] -> 2.566 V
        """

        if len(registers) < 2:
            raise RuntimeError(
                f"Expected 2 registers, got {len(registers)}."
            )

        packed = struct.pack(
            ">HH",
            registers[1],
            registers[0],
        )

        value = struct.unpack(">f", packed)[0]

        if not math.isfinite(value):
            raise RuntimeError(
                f"Decoded analog value is invalid: {value}"
            )

        return value

    def read_ai2_voltage(self) -> float:
        """Read live voltage from AI2."""

        result = self.client.read_holding_registers(
            address=self.settings.ai2_address,
            count=2,
            device_id=self.settings.adam_slave_id,
        )

        if result.isError():
            raise RuntimeError(f"Could not read AI2: {result}")

        registers = result.registers[:2]

        return self._decode_cdab_float(registers)

    # ========================================================
    # CLOSE
    # ========================================================
    def close(self) -> None:
        self.client.close()