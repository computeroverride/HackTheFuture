import math
import struct
import time

from pymodbus.client import ModbusTcpClient


ADAM_IP = "10.0.0.1"
ADAM_PORT = 5020
DEVICE_ID = 1

# AI register offsets
AI0_ADDRESS = 30   # Sound sensor
AI2_ADDRESS = 34   # Thermistor
AI4_ADDRESS = 38   # Photocell

# DI coil offsets
DI0_ADDRESS = 0    # Crash sensor
DI2_ADDRESS = 2    # Button switch


def decode_cdab_float(register_1: int, register_2: int) -> float:
    raw_bytes = struct.pack(
        ">HH",
        register_2,
        register_1,
    )

    value = struct.unpack(">f", raw_bytes)[0]

    if not math.isfinite(value):
        return 0.0

    return value


def read_ai_voltage(client: ModbusTcpClient, address: int) -> float:
    result = client.read_holding_registers(
        address=address,
        count=2,
        device_id=DEVICE_ID,
    )

    if result.isError():
        raise RuntimeError(f"Could not read AI at address {address}: {result}")

    return decode_cdab_float(
        result.registers[0],
        result.registers[1],
    )


def read_di(client: ModbusTcpClient, address: int) -> bool:
    result = client.read_coils(
        address=address,
        count=1,
        device_id=DEVICE_ID,
    )

    if result.isError():
        raise RuntimeError(f"Could not read DI at address {address}: {result}")

    return bool(result.bits[0])


def main() -> None:
    client = ModbusTcpClient(
        host=ADAM_IP,
        port=ADAM_PORT,
        timeout=3,
    )

    print("Connecting to ADAM-6717...")

    if not client.connect():
        print("Cannot connect to ADAM.")
        return

    print("Connected.")
    print("Testing inputs only.")
    print("Press Ctrl+C to stop.")
    print()

    try:
        while True:
            sound_voltage = read_ai_voltage(client, AI0_ADDRESS)
            thermistor_voltage = read_ai_voltage(client, AI2_ADDRESS)
            photocell_voltage = read_ai_voltage(client, AI4_ADDRESS)

            crash_pressed = read_di(client, DI0_ADDRESS)
            button_pressed = read_di(client, DI2_ADDRESS)

            print(
                f"Sound AI0={sound_voltage:6.3f} V | "
                f"Thermistor AI2={thermistor_voltage:6.3f} V | "
                f"Photocell AI4={photocell_voltage:6.3f} V | "
                f"Crash DI0={'ON ' if crash_pressed else 'OFF'} | "
                f"Button DI2={'ON ' if button_pressed else 'OFF'}"
            )

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")

    finally:
        client.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()