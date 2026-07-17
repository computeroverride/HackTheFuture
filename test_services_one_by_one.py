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

        thermistor_ai2 = ProductDetectorAI2(
            adam=adam,
            settings=settings,
            detect_threshold_voltage=1.0,
        )

        conveyor_photocell = CameraPhotocellAI4(
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
        print("Motor sound AI0 will control Fan DO0.")
        print("Camera station is left blank for future code.")
        print("Press Ctrl+C to stop.")
        print()

        while True:
            # ------------------------------------------------
            # ENTRY ZONE
            # Button gives product ID.
            # ------------------------------------------------

            product_id = entry_button.get_product_id_if_pressed()
            button_pressed = entry_button.read_button()

            # ------------------------------------------------
            # THERMISTOR
            # AI2 reading.
            # ------------------------------------------------

            ai2_voltage = thermistor_ai2.read_voltage()
            ai2_detected = thermistor_ai2.is_product_detected()

            # ------------------------------------------------
            # CONVEYOR BELT
            # Photocell AI4 reading.
            # ------------------------------------------------

            ai4_voltage = conveyor_photocell.read_voltage()
            conveyor_detected = (
                conveyor_photocell.is_at_camera_station()
            )

            # ------------------------------------------------
            # CAMERA STATION
            # Blank for future ML / camera code.
            # ------------------------------------------------

            camera_station_status = "NOT CODED YET"

            # ------------------------------------------------
            # MOTOR AREA
            # Sound sensor controls fan.
            # ------------------------------------------------

            sound_voltage = motor_sound.read_sound_value()

            motor_sound_active = motor_sound.is_motor_loud(
                threshold_voltage=0.2,
            )

            if motor_sound_active:
                fan_relay.turn_on()
            else:
                fan_relay.turn_off()

            fan_on = fan_relay.is_on()

            # ------------------------------------------------
            # OTHERS
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

            print("THERMISTOR")
            print(f"AI2 voltage: {ai2_voltage:.3f} V")
            print(f"AI2 detected / above threshold: {ai2_detected}")

            print()

            print("CONVEYOR BELT")
            print(f"Photocell AI4 voltage: {ai4_voltage:.3f} V")
            print(f"Conveyor belt detected: {conveyor_detected}")

            print()

            print("CAMERA STATION")
            print(f"Status: {camera_station_status}")

            print()

            print("MOTOR AREA")
            print(f"Sound AI0 voltage: {sound_voltage:.3f} V")
            print(f"Motor sound active: {motor_sound_active}")
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
        # Safety: turn fan off when this test stops.
        try:
            fan_relay.turn_off()
            print("Fan DO0 turned OFF.")
        except Exception:
            pass

        adam.close()
        print("Connection closed.")


if __name__ == "__main__":
    main()