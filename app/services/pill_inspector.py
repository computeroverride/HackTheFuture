from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from app.ml.pill_inference import PillPredictor


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL_PATH = (
    PROJECT_ROOT
    / "storage"
    / "models"
    / "pill_classifier.pt"
)

DEFAULT_FAILURE_DIR = (
    PROJECT_ROOT
    / "storage"
    / "failures"
)


def open_camera(camera_index: int = 0):
    for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
        for index in [camera_index, 0, 1, 2]:
            capture = cv2.VideoCapture(index, backend)
            if not capture.isOpened():
                continue

            success, _ = capture.read()
            if success:
                return capture

            capture.release()

    raise RuntimeError(
        "Could not open or read from webcam. "
        f"Tried camera index {camera_index} with available OpenCV backends."
    )


class PillInspector:
    def __init__(
        self,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        camera_index: int = 0,
        burst_count: int = 3,
        burst_delay_seconds: float = 0.12,
        min_confidence: float = 0.60,
        failure_dir: Path | str = DEFAULT_FAILURE_DIR,
    ) -> None:
        self.predictor = PillPredictor(
            model_path,
            min_confidence=min_confidence,
        )

        self.burst_count = burst_count
        self.burst_delay_seconds = (
            burst_delay_seconds
        )

        self.failure_dir = Path(failure_dir)

        self.camera = open_camera(camera_index)

        if not self.camera.isOpened():
            raise RuntimeError(
                f"Could not open camera index "
                f"{camera_index}"
            )

    @staticmethod
    def sharpness_score(frame) -> float:
        """
        Larger Laplacian variance generally means
        the image has sharper edges.
        """

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

    def capture_sharpest_frame(self):
        captured_frames = []

        for _ in range(self.burst_count):
            success, frame = self.camera.read()

            if not success:
                raise RuntimeError(
                    "Webcam frame capture failed"
                )

            captured_frames.append(frame.copy())

            time.sleep(
                self.burst_delay_seconds
            )

        sharpest_frame = max(
            captured_frames,
            key=self.sharpness_score,
        )

        return sharpest_frame

    def inspect(
        self,
        product_id: str,
    ) -> dict[str, Any]:
        frame = self.capture_sharpest_frame()

        result = self.predictor.predict_frame(
            frame
        )

        result["product_id"] = product_id
        result["sharpness"] = (
            self.sharpness_score(frame)
        )

        result["saved_image"] = None

        # Pass images are not retained.
        # Only the selected sharpest failure image
        # is stored.
        if not result["is_pass"]:
            self.failure_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )

            filename = (
                f"{product_id}_"
                f"{result['final_label']}_"
                f"{timestamp}.jpg"
            )

            output_path = (
                self.failure_dir / filename
            )

            saved = cv2.imwrite(
                str(output_path),
                frame,
            )

            if not saved:
                raise RuntimeError(
                    "Could not save failure image: "
                    f"{output_path}"
                )

            result["saved_image"] = str(
                output_path
            )

        return result

    def close(self) -> None:
        if self.camera.isOpened():
            self.camera.release()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exception_type,
        exception_value,
        traceback,
    ):
        self.close()