import time

from app.adam import Adam6717Connection
from app.settings import load_settings

from app.services.entry_button import EntryButton
from app.services.product_detector_ai2 import ProductDetectorAI2
from app.services.camera_photocell_ai4 import CameraPhotocellAI4
from app.services.motor_sound_ai0 import MotorSoundAI0
from app.services.crash_sensor_di0 import CrashSensorDI0
from app.services.fan_relay_do0 import FanRelayDO0
from app.services.buzzer_do2 import BuzzerDO2


def main() -> None:
    settings = load_settings()

    adam = Adam6717Connection(settings)

    try:
        adam.connect()

        # ----------------------------------------------------
        # Create one object for each sensor/output service.
        # ----------------------------------------------------

        entry_button = EntryButton(
            adam=adam,
            settings=settings,
        )

        product_detector = ProductDetectorAI2(
            adam=adam,
            settings=settings,
            detect_threshold_voltage=1.0,
        )

        camera_photocell = CameraPhotocellAI4(
            adam=adam,
            settings=settings,
            detect_threshold_voltage=0.3,
        )

        motor_sound = MotorSoundAI0(
            adam=adam,
            settings=settings,
        )

        crash_sensor = CrashSensorDI0(
            adam=adam,
            settings=settings,
        )

        fan_relay = FanRelayDO0(
            adam=adam,
            settings=settings,
        )

        buzzer = BuzzerDO2(
            adam=adam,
            settings=settings,
        )

        print()
        print("Testing all services one by one.")
        print("This test will only READ values first.")
        print("It will NOT turn on fan or buzzer.")
        print("Press Ctrl+C to stop.")
        print()

        while True:
            # ------------------------------------------------
            # Entry zone
            # ------------------------------------------------

            product_id = entry_button.get_product_id_if_pressed()
            button_pressed = entry_button.read_button()

            # ------------------------------------------------
            # Conveyor belt
            # ------------------------------------------------

            ai2_voltage = product_detector.read_voltage()
            product_detected = product_detector.is_product_detected()

            ai4_voltage = camera_photocell.read_voltage()
            at_camera_station = camera_photocell.is_at_camera_station()

            # ------------------------------------------------
            # Motor area
            # ------------------------------------------------

            sound_voltage = motor_sound.read_sound_value()
            motor_loud = motor_sound.is_motor_loud(
                threshold_voltage=0.2,
            )

            fan_on = fan_relay.is_on()

            # ------------------------------------------------
            # Others
            # ------------------------------------------------

            crash_detected = crash_sensor.is_crash_detected()
            buzzer_on = buzzer.is_buzzing()

            # ------------------------------------------------
            # Print result
            # ------------------------------------------------

            print("--------------------------------------------------")

            print("ENTRY ZONE")
            print(f"Button DI2 pressed: {button_pressed}")
            print(f"New product ID: {product_id}")

            print()

            print("CONVEYOR BELT")
            print(f"AI2 product sensor voltage: {ai2_voltage:.3f} V")
            print(f"Product detected by AI2: {product_detected}")

            print()

            print("CAMERA STATION")
            print(f"Photocell AI4 voltage: {ai4_voltage:.3f} V")
            print(f"Product at camera station: {at_camera_station}")

            print()

            print("MOTOR AREA")
            print(f"Sound AI0 voltage: {sound_voltage:.3f} V")
            print(f"Motor sound active: {motor_loud}")
            print(f"Fan relay DO0 is ON: {fan_on}")

            print()

            print("OTHERS")
            print(f"Crash DI0 detected: {crash_detected}")
            print(f"Buzzer DO2 is ON: {buzzer_on}")

            print("--------------------------------------------------")
            print()

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("Stopped by user.")

    finally:
        adam.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()