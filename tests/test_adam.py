import time

from app.settings import load_settings
from app.adam import Adam6717Connection

settings = load_settings()
adam = Adam6717Connection(settings)
adam.connect()

print("Reading inputs for 10 seconds...")
start = time.monotonic()

while time.monotonic() - start < 10:
    camera_sensor = adam.read_camera_sensor()
    end_sensor = adam.read_end_sensor()
    button = adam.read_button()

    print(
        f"camera_sensor={camera_sensor} | "
        f"end_sensor={end_sensor} | "
        f"button={button}"
    )

    time.sleep(0.5)

print("Testing servo trigger DO...")
adam.write_servo_trigger(True)
time.sleep(0.2)
adam.write_servo_trigger(False)

print("Testing buzzer DO...")
adam.write_buzzer(True)
time.sleep(0.4)
adam.write_buzzer(False)

adam.close()
print("ADAM test done.")