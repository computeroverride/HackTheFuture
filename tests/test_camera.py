import sys
from pathlib import Path
import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.pill_inspector import open_camera

camera = open_camera(1)

if not camera.isOpened():
    raise RuntimeError("Could not open webcam index 1")

print("Press ENTER to capture an image, or ESC to quit.")

i = 0
while True:
    ok, frame = camera.read()
    if not ok:
        raise RuntimeError("Could not read frame")

    # Show live preview
    cv2.imshow("Camera Preview", frame)

    # Wait for key press
    key = cv2.waitKey(1) & 0xFF

    if key == 13:  # ENTER key
        i += 1
        output_path = PROJECT_ROOT / f"test_webcam_{i}.jpg"
        cv2.imwrite(str(output_path), frame)
        print(f"Saved {output_path.name}")

    elif key == 27:  # ESC key
        break

camera.release()
cv2.destroyAllWindows()
print("Camera test done.")
