from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_ROOT = (
    PROJECT_ROOT
    / "storage"
    / "datasets"
)

CAMERA_INDEX = 1
BURST_COUNT = 3
BURST_DELAY_SECONDS = 0.12

# The script starts in the pass class.
current_class = "fail_defect"

VALID_CLASSES = {
    "pass",
    "fail_defect",
    "fail_different",
}


def calculate_sharpness(frame) -> float:
    grayscale = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY,
    )

    return float(
        cv2.Laplacian(
            grayscale,
            cv2.CV_64F,
        ).var()
    )


def capture_sharpest_frame(camera):
    frames = []

    for _ in range(BURST_COUNT):
        success, frame = camera.read()

        if not success:
            raise RuntimeError(
                "Failed to capture webcam image."
            )

        frames.append(frame.copy())
        time.sleep(BURST_DELAY_SECONDS)

    return max(
        frames,
        key=calculate_sharpness,
    )


def save_frame(frame, class_name: str) -> Path:
    if class_name not in VALID_CLASSES:
        raise ValueError(
            f"Invalid dataset class: {class_name}"
        )

    output_folder = DATASET_ROOT / class_name

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    filename = f"{class_name}_{timestamp}.jpg"
    output_path = output_folder / filename

    saved = cv2.imwrite(
        str(output_path),
        frame,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save image to {output_path}"
        )

    return output_path


def main() -> None:
    global current_class

    # CAP_DSHOW normally works well for Windows webcams.
    camera = cv2.VideoCapture(
        CAMERA_INDEX,
        cv2.CAP_DSHOW,
    )

    if not camera.isOpened():
        raise RuntimeError(
            f"Could not open camera index {CAMERA_INDEX}"
        )

    saved_count = {
        "good": 0,
        "fail_defect": 0,
        "fail_different": 0,
    }

    status_text = "Ready to capture"

    print("Dataset camera started.")
    print()
    print("Controls:")
    print("  SPACE = capture and save")
    print("  1     = select good")
    print("  2     = select fail_defect")
    print("  3     = select fail_different")
    print("  Q/ESC = quit")
    print()
    print("Current class: good")

    try:
        while True:
            success, frame = camera.read()

            if not success:
                raise RuntimeError(
                    "Could not read webcam frame."
                )

            display_frame = frame.copy()

            cv2.putText(
                display_frame,
                f"Class: {current_class}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )

            cv2.putText(
                display_frame,
                "SPACE: Save | 1/2/3: Class | Q: Quit",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

            cv2.putText(
                display_frame,
                status_text,
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

            cv2.imshow(
                "Pill Dataset Collector",
                display_frame,
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                break

            if key == ord("1"):
                current_class = "good"
                status_text = "Selected good"
                print("\nCurrent class: good")

            elif key == ord("2"):
                current_class = "fail_defect"
                status_text = "Selected fail_defect"
                print("\nCurrent class: fail_defect")

            elif key == ord("3"):
                current_class = "fail_different"
                status_text = "Selected fail_different"
                print("\nCurrent class: fail_different")

            elif key == 32:
                print(
                    f"\nCapturing {current_class} image..."
                )

                sharpest_frame = capture_sharpest_frame(
                    camera
                )

                sharpness = calculate_sharpness(
                    sharpest_frame
                )

                output_path = save_frame(
                    sharpest_frame,
                    current_class,
                )

                saved_count[current_class] += 1

                status_text = (
                    f"Saved {current_class} "
                    f"#{saved_count[current_class]}"
                )

                print(f"Saved: {output_path}")
                print(f"Sharpness: {sharpness:.2f}")
                print(
                    f"Session count: "
                    f"{saved_count[current_class]}"
                )

    finally:
        camera.release()
        cv2.destroyAllWindows()

        print("\nCollection stopped.")
        print("Images saved this session:")

        for class_name, count in saved_count.items():
            print(f"  {class_name}: {count}")


if __name__ == "__main__":
    main()