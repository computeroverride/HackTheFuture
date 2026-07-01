import time
from pymodbus.client import ModbusTcpClient

# -----------------------------
# ADAM-6717 CONNECTION SETTINGS
# -----------------------------
ADAM_IP = "11.0.0.1"
ADAM_PORT = 5020
SLAVE_ID = 1

# Official ADAM-6717 Modbus map:
# DI2 = address 00003  -> PyModbus offset 2
# DO0 = address 00017  -> PyModbus offset 16
DI2_ADDRESS = 2
DO0_ADDRESS = 16

POLL_INTERVAL_SECONDS = 0.05
DEBOUNCE_SECONDS = 0.20


def read_di2(client: ModbusTcpClient) -> bool:
    """Return True while DI2 button is pressed."""
    # ADAM-6717 firmware exposes its 0X I/O map through Read Coils.
    result = client.read_coils(
        address=DI2_ADDRESS,
        count=1,
        device_id=SLAVE_ID,
    )

    if result.isError():
        raise RuntimeError(f"Could not read DI2: {result}")

    return bool(result.bits[0])


def read_do0(client: ModbusTcpClient) -> bool:
    """Read current physical state of DO0."""
    result = client.read_coils(
        address=DO0_ADDRESS,
        count=1,
        device_id=SLAVE_ID,
    )

    if result.isError():
        raise RuntimeError(f"Could not read DO0: {result}")

    return bool(result.bits[0])


def write_do0(client: ModbusTcpClient, fan_on: bool) -> None:
    """Set DO0. True = relay/fan ON; False = relay/fan OFF."""
    result = client.write_coil(
        address=DO0_ADDRESS,
        value=fan_on,
        device_id=SLAVE_ID,
    )

    if result.isError():
        raise RuntimeError(f"Could not write DO0: {result}")


def main():
    client = ModbusTcpClient(
        host=ADAM_IP,
        port=ADAM_PORT,
        timeout=3,
    )

    if not client.connect():
        raise ConnectionError(
            f"Cannot connect to ADAM-6717 at {ADAM_IP}:{ADAM_PORT}"
        )

    try:
        # Keep the relay's current physical state when Python starts.
        fan_on = read_do0(client)

        # Prevent a toggle immediately on startup if the button is being held.
        previous_button_state = read_di2(client)

        print("Connected to ADAM-6717.")
        print(f"Fan starts as: {'ON' if fan_on else 'OFF'}")
        print("Press DI2 once to toggle the fan. Press Ctrl+C to stop.")

        last_toggle_time = 0.0

        while True:
            button_pressed = read_di2(client)
            now = time.monotonic()

            # Detect a new press only: released -> pressed
            new_press = button_pressed and not previous_button_state

            # Debounce so a single press cannot toggle repeatedly
            if new_press and (now - last_toggle_time) >= DEBOUNCE_SECONDS:
                fan_on = not fan_on
                write_do0(client, fan_on)

                print(
                    f"Button pressed -> Fan {'ON' if fan_on else 'OFF'}"
                )

                last_toggle_time = now

            previous_button_state = button_pressed
            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopped. Leaving DO0 in its current state.")

    finally:
        client.close()


if __name__ == "__main__":
    main()