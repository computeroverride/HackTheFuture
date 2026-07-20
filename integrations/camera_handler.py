import shutil
import time
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

from app.settings import PROJECT_ROOT, Settings


class CameraHandler:
    def __init__(self, settings: Settings):
        self.settings = settings

        self.storage_dir = PROJECT_ROOT / "storage" / "training"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.faulty_dir = PROJECT_ROOT / "storage" / "faulty"
        self.faulty_dir.mkdir(parents=True, exist_ok=True)

    def capture_burst(self, product_id: int) -> list[Path]:
        if cv2 is None:
            raise RuntimeError(
                "opencv-python is not installed. Run: py -m pip install opencv-python"
            )

        camera = cv2.VideoCapture(self.settings.camera_index)
        if not camera.isOpened():
            raise RuntimeError(
                f"Could not open webcam CAMERA_INDEX={self.settings.camera_index}"
            )

        image_paths: list[Path] = []

        try:
            # Warm up a few frames so brightness/exposure is less random.
            for _ in range(5):
                camera.read()

            for index in range(1, self.settings.camera_burst_count + 1):
                ok, frame = camera.read()

                if not ok:
                    raise RuntimeError("Webcam frame capture failed")

                path = self.storage_dir / f"P{product_id:03d}_{index}.jpg"
                cv2.imwrite(str(path), frame)
                image_paths.append(path)

                time.sleep(self.settings.camera_burst_gap_seconds)

        finally:
            camera.release()

        return image_paths

    def choose_sharpest_image(self, image_paths: list[Path]) -> Path:
        if cv2 is None:
            raise RuntimeError(
                "opencv-python is not installed. Run: py -m pip install opencv-python"
            )

        best_path = None
        best_score = -1.0

        for path in image_paths:
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

            if image is None:
                continue

            # Higher Laplacian variance = sharper image.
            score = cv2.Laplacian(image, cv2.CV_64F).var()

            if score > best_score:
                best_score = score
                best_path = path

        if best_path is None:
            raise RuntimeError("Could not select sharpest image")

        return best_path

    def keep_faulty_image(self, product_id: int, image_path: Path) -> Path:
        destination = self.faulty_dir / f"P{product_id:03d}_faulty_best.jpg"
        shutil.copy2(image_path, destination)
        return destination