from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2

from app.services.pill_inspector import open_camera
from app.settings import load_settings


# Edit this, then rerun, to switch which class you are collecting.
# Must match one of app/ml/training.py's EXPECTED_CLASSES.
DESTINATION_CLASS = "pass"  

VALID_CLASSES = {"pass", "fail_defect", "fail_different"}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = PROJECT_ROOT / "storage" / "datasets"


def main() -> None:
    if DESTINATION_CLASS not in VALID_CLASSES:
        raise ValueError(
            f"DESTINATION_CLASS must be one of {sorted(VALID_CLASSES)}, "
            f"got: {DESTINATION_CLASS!r}"
        )

    output_dir = DATASET_ROOT / DESTINATION_CLASS
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = load_settings()
    camera = open_camera(settings.camera_index)
    saved_count = 0

    print(f"Collecting class: {DESTINATION_CLASS}")
    print(f"Saving to: {output_dir}")
    print("SPACE = save frame | Q/ESC = quit\n")

    try:
        while True:
            success, frame = camera.read()
            if not success:
                raise RuntimeError("Could not read webcam frame.")

            display_frame = frame.copy()
            cv2.putText(
                display_frame,
                f"Class: {DESTINATION_CLASS} | Saved: {saved_count}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                display_frame,
                "SPACE: Save | Q: Quit",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
            )

            cv2.imshow("Dataset Collector", display_frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                break

            if key == 32:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                output_path = (
                    output_dir / f"{DESTINATION_CLASS}_{timestamp}.jpg"
                )

                if not cv2.imwrite(str(output_path), frame):
                    print(f"Failed to save: {output_path}")
                    continue

                saved_count += 1
                print(f"Saved ({saved_count}): {output_path}")

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print(f"\nDone. Saved {saved_count} image(s) to {output_dir}")


if __name__ == "__main__":
    main()
