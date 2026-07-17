from __future__ import annotations

import cv2

from app.services.pill_inspector import PillInspector


CAMERA_INDEX = 1
CONFIDENCE_THRESHOLD = 0.60


def main() -> None:
    product_number = 1
    latest_result_text = "No inspection yet"

    try:
        with PillInspector(
            camera_index=CAMERA_INDEX,
            burst_count=3,
            burst_delay_seconds=0.12,
            min_confidence=CONFIDENCE_THRESHOLD,
        ) as inspector:

            print("Camera started.")
            print("Press SPACE to inspect the pill.")
            print("Press Q or ESC to quit.")

            while True:
                success, frame = inspector.camera.read()

                if not success:
                    raise RuntimeError(
                        "Unable to capture webcam frame."
                    )

                display_frame = frame.copy()

                cv2.putText(
                    display_frame,
                    "SPACE: Inspect | Q: Quit",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    (255, 255, 255),
                    2,
                )

                cv2.putText(
                    display_frame,
                    latest_result_text,
                    (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.70,
                    (255, 255, 255),
                    2,
                )

                cv2.imshow(
                    "Pill Camera Test",
                    display_frame,
                )

                key = cv2.waitKey(1) & 0xFF

                # Q or Escape
                if key == ord("q") or key == 27:
                    break

                # Space bar
                if key == 32:
                    product_id = (
                        f"P-{product_number:03d}"
                    )

                    print(
                        f"\nInspecting {product_id}..."
                    )

                    result = inspector.inspect(
                        product_id=product_id
                    )

                    latest_result_text = (
                        f"{result['final_label']} | "
                        f"{result['confidence']:.1%}"
                    )

                    print("-------------------------")
                    print(
                        f"Product ID: "
                        f"{result['product_id']}"
                    )
                    print(
                        f"Raw prediction: "
                        f"{result['raw_label']}"
                    )
                    print(
                        f"Final result: "
                        f"{result['final_label']}"
                    )
                    print(
                        f"Confidence: "
                        f"{result['confidence']:.2%}"
                    )
                    print(
                        f"Pass: {result['is_pass']}"
                    )
                    print(
                        f"Sharpness: "
                        f"{result['sharpness']:.2f}"
                    )
                    print(
                        f"Saved image: "
                        f"{result['saved_image']}"
                    )

                    print("Class probabilities:")

                    for class_name, probability in (
                        result["probabilities"].items()
                    ):
                        print(
                            f"  {class_name}: "
                            f"{probability:.2%}"
                        )

                    product_number += 1

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()