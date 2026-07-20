import cv2

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    raise RuntimeError("Could not open webcam index 0")

for i in range(3):
    ok, frame = camera.read()

    if not ok:
        raise RuntimeError("Could not read frame")

    cv2.imwrite(f"test_webcam_{i + 1}.jpg", frame)
    print(f"Saved test_webcam_{i + 1}.jpg")

camera.release()
print("Camera test done.")