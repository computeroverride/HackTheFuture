import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.pill_inspector import open_camera

camera = open_camera(1)

if not camera.isOpened():
    raise RuntimeError("Could not open webcam index 0")

for i in range(3):
    ok, frame = camera.read()

    if not ok:
        raise RuntimeError("Could not read frame")

    output_path = PROJECT_ROOT / f"test_webcam_{i + 1}.jpg"
    cv2.imwrite(str(output_path), frame)
    print(f"Saved {output_path.name}")

camera.release()
print("Camera test done.")