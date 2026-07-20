from __future__ import annotations

import os
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import cv2


# =========================================================
# Project paths
# =========================================================

# This file is located at:
# project_root/tests/test_photocell_camera.py

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

# Images will be saved under:
# project_root/tests/test_images/
OUTPUT_DIR = TESTS_DIR / "test_images"

# Allow this test file to import modules from project_root/app.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.adam import Adam6717Connection
from app.settings import load_settings


# =========================================================
# Test settings
# =========================================================

# Reading all these addresses is required because your ADAM
# only produces a changing value at address 38 when the full
# sequence is scanned.
AI_ADDRESSES = [
    30,
    32,
    34,
    36,
    38,
    40,
    42,
]

PHOTOCELL_ADDRESS = 38

# Product is detected when AI4 drops below this value.
PHOTOCELL_THRESHOLD_VOLTAGE = 0.1000

# Read the ADAM repeatedly.
SENSOR_READ_INTERVAL_SECONDS = 0.10

# Print the photocell status every 3 seconds.
STATUS_PRINT_INTERVAL_SECONDS = 3.0

# After the photocell becomes clear, it must remain clear
# for this duration before another capture is allowed.
PHOTOCELL_REARM_SECONDS = 2.0


# =========================================================
# ADAM reading
# =========================================================

def read_all_ai_addresses(
    adam: Adam6717Connection,
) -> dict[int, float]:
    """
    Read every AI address in the proven working sequence.

    The returned dictionary contains:

        {
            30: value,
            32: value,
            ...
            38: photocell value,
            ...
        }
    """
    readings: dict[int, float] = {}

    for address in AI_ADDRESSES:
        readings[address] = adam.read_ai_voltage(address)

    return readings


def read_photocell_voltage(
    adam: Adam6717Connection,
) -> float:
    """
    Perform the complete AI scan, then return only address 38.
    """
    readings = read_all_ai_addresses(adam)

    if PHOTOCELL_ADDRESS not in readings:
        raise RuntimeError(
            f"Photocell address {PHOTOCELL_ADDRESS} "
            "was not returned by the AI scan."
        )

    return readings[PHOTOCELL_ADDRESS]


# =========================================================
# Camera
# =========================================================

def open_camera(
    camera_index: int,
) -> cv2.VideoCapture:
    if os.name == "nt":
        camera = cv2.VideoCapture(
            camera_index,
            cv2.CAP_DSHOW,
        )
    else:
        camera = cv2.VideoCapture(camera_index)

    if not camera.isOpened():
        camera.release()

        raise RuntimeError(
            f"Could not open camera index {camera_index}. "
            "Close other programs using the camera or change "
            "CAMERA_INDEX in .env."
        )

    # Discard some startup frames to allow exposure and focus
    # to stabilise.
    for _ in range(10):
        camera.read()
        time.sleep(0.03)

    success, frame = camera.read()

    if not success or frame is None:
        camera.release()

        raise RuntimeError(
            f"Camera index {camera_index} opened, "
            "but no image could be read."
        )

    return camera


def capture_sharpest_image(
    camera: cv2.VideoCapture,
    product_number: int,
    burst_count: int,
    burst_gap_seconds: float,
) -> Path:
    """
    Capture several frames and save only the sharpest frame.

    This function runs in a background thread so the main loop
    can continue reading the ADAM while the camera is capturing.
    """
    captured_frames = []

    for frame_number in range(
        1,
        burst_count + 1,
    ):
        success, frame = camera.read()

        if not success or frame is None:
            print(
                f"Frame {frame_number}/{burst_count}: "
                "capture failed",
                flush=True,
            )
        else:
            gray_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2GRAY,
            )

            sharpness = float(
                cv2.Laplacian(
                    gray_frame,
                    cv2.CV_64F,
                ).var()
            )

            captured_frames.append(
                (sharpness, frame)
            )

            print(
                f"Frame {frame_number}/{burst_count}: "
                f"sharpness={sharpness:.2f}",
                flush=True,
            )

        if frame_number < burst_count:
            time.sleep(burst_gap_seconds)

    if not captured_frames:
        raise RuntimeError(
            "No usable camera frames were captured."
        )

    sharpness, sharpest_frame = max(
        captured_frames,
        key=lambda item: item[0],
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    image_path = OUTPUT_DIR / (
        f"P{product_number:03d}_{timestamp}.jpg"
    )

    # Avoid overwriting if two images receive the same timestamp.
    duplicate_number = 1

    while image_path.exists():
        image_path = OUTPUT_DIR / (
            f"P{product_number:03d}_"
            f"{timestamp}_{duplicate_number}.jpg"
        )

        duplicate_number += 1

    saved = cv2.imwrite(
        str(image_path),
        sharpest_frame,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save image: {image_path}"
        )

    print(
        f"Selected sharpness: {sharpness:.2f}",
        flush=True,
    )

    print(
        f"Saved image: {image_path}",
        flush=True,
    )

    return image_path


# =========================================================
# Main test
# =========================================================

def main() -> None:
    settings = load_settings()

    adam = Adam6717Connection(settings)
    camera: cv2.VideoCapture | None = None

    # Only one camera burst may run at one time.
    camera_executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="camera-burst",
    )

    capture_future: Future[Path] | None = None

    try:
        adam.connect()

        camera = open_camera(
            settings.camera_index
        )

        print()
        print("Photocell + camera test started.")
        print(
            f"AI scan addresses: {AI_ADDRESSES}"
        )
        print(
            f"Photocell address: {PHOTOCELL_ADDRESS}"
        )
        print(
            f"Covered condition: voltage below "
            f"{PHOTOCELL_THRESHOLD_VOLTAGE:.4f} V"
        )
        print(
            f"Standby condition: voltage at or above "
            f"{PHOTOCELL_THRESHOLD_VOLTAGE:.4f} V"
        )
        print(
            f"Camera index: {settings.camera_index}"
        )
        print(
            f"Burst count: "
            f"{settings.camera_burst_count}"
        )
        print(
            f"Burst gap: "
            f"{settings.camera_burst_gap_seconds:.2f} seconds"
        )
        print(
            f"Image folder: {OUTPUT_DIR}"
        )
        print()
        print(
            "Leave the photocell uncovered first."
        )
        print(
            "Cover it to trigger one camera burst."
        )
        print(
            "The ADAM will continue being scanned "
            "during the camera burst."
        )
        print(
            "Press Ctrl+C to stop."
        )
        print()

        product_number = 1
        last_status_print = 0.0
        clear_started_at: float | None = None

        # Perform the full scan for the initial reading.
        initial_voltage = read_photocell_voltage(adam)

        # Do not trigger immediately if the program starts while
        # the photocell is already covered.
        armed = (
            initial_voltage
            >= PHOTOCELL_THRESHOLD_VOLTAGE
        )

        if not armed:
            print(
                f"Initial photocell value is "
                f"{initial_voltage:.4f} V."
            )
            print(
                "The photocell appears covered."
            )
            print(
                "Uncover it first to arm the camera."
            )
            print()

        while True:
            # Read all AI addresses every loop.
            photocell_voltage = read_photocell_voltage(
                adam
            )

            product_detected = (
                photocell_voltage
                < PHOTOCELL_THRESHOLD_VOLTAGE
            )

            now = time.monotonic()

            # Check whether the background burst has completed.
            if (
                capture_future is not None
                and capture_future.done()
            ):
                try:
                    saved_path = capture_future.result()

                    print(
                        f"Camera burst completed: "
                        f"{saved_path}",
                        flush=True,
                    )

                except Exception as error:
                    print(
                        f"Camera burst failed: {error}",
                        flush=True,
                    )

                capture_future = None

            # Print live status every 3 seconds.
            if (
                now - last_status_print
                >= STATUS_PRINT_INTERVAL_SECONDS
            ):
                photocell_status = (
                    "COVERED"
                    if product_detected
                    else "STANDBY"
                )

                camera_status = (
                    "CAPTURING"
                    if capture_future is not None
                    else "IDLE"
                )

                if armed:
                    system_status = "ARMED"

                elif product_detected:
                    system_status = (
                        "WAITING FOR PHOTOCELL TO CLEAR"
                    )

                elif clear_started_at is not None:
                    clear_duration = (
                        now - clear_started_at
                    )

                    system_status = (
                        f"COOLDOWN "
                        f"{clear_duration:.1f}/"
                        f"{PHOTOCELL_REARM_SECONDS:.1f}s"
                    )

                else:
                    system_status = "NOT ARMED"

                print(
                    f"{datetime.now().strftime('%H:%M:%S')} | "
                    f"AI4={photocell_voltage:.4f} V | "
                    f"photocell={photocell_status} | "
                    f"system={system_status} | "
                    f"camera={camera_status}",
                    flush=True,
                )

                last_status_print = now

            # -------------------------------------------------
            # Product detected
            # -------------------------------------------------

            if (
                product_detected
                and armed
                and capture_future is None
            ):
                current_product_number = product_number
                product_number += 1

                print()
                print(
                    f"Photocell covered: "
                    f"{photocell_voltage:.4f} V",
                    flush=True,
                )

                print(
                    f"Starting camera burst for "
                    f"P{current_product_number:03d}...",
                    flush=True,
                )

                capture_future = camera_executor.submit(
                    capture_sharpest_image,
                    camera,
                    current_product_number,
                    settings.camera_burst_count,
                    settings.camera_burst_gap_seconds,
                )

                # Immediately disarm to prevent repeated captures
                # while the same product remains over the sensor.
                armed = False
                clear_started_at = None

            # -------------------------------------------------
            # Photocell is uncovered
            # -------------------------------------------------

            if not product_detected:
                if not armed:
                    if clear_started_at is None:
                        clear_started_at = now

                        print(
                            "Photocell returned to standby. "
                            "Rearm timer started.",
                            flush=True,
                        )

                    clear_duration = (
                        now - clear_started_at
                    )

                    # Rearm only when:
                    # 1. the sensor remained clear for 2 seconds;
                    # 2. the previous camera burst is complete.
                    if (
                        clear_duration
                        >= PHOTOCELL_REARM_SECONDS
                        and capture_future is None
                    ):
                        armed = True
                        clear_started_at = None

                        print(
                            "Photocell cooldown complete. "
                            "Camera armed for the next product.",
                            flush=True,
                        )

            # The photocell became covered again before the
            # rearm timer completed.
            elif product_detected and not armed:
                clear_started_at = None

            time.sleep(
                SENSOR_READ_INTERVAL_SECONDS
            )

    except KeyboardInterrupt:
        print()
        print(
            "Photocell + camera test stopped."
        )

    finally:
        # Finish any ongoing camera burst before closing.
        camera_executor.shutdown(
            wait=True,
            cancel_futures=False,
        )

        if camera is not None:
            camera.release()

        adam.close()


if __name__ == "__main__":
    main()