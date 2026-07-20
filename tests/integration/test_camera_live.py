from __future__ import annotations

import pytest
from pathlib import Path
import cv2

pytestmark = [pytest.mark.integration, pytest.mark.camera]


def test_camera_opens_and_saves_frame() -> None:
    from app.services.pill_inspector import open_camera
    from app.settings import load_settings

    settings = load_settings()
    camera = open_camera(settings.camera_index)

    try:
        success, frame = camera.read()
        assert success is True
        assert frame is not None
        assert frame.size > 0

        project_root = Path(__file__).resolve().parents[1]
        images_dir = project_root / "test_images"
        images_dir.mkdir(exist_ok=True)

        output_path = images_dir / "captured_frame.jpg"
        cv2.imwrite(str(output_path), frame)
        print(f"Saved captured frame to {output_path}")
    finally:
        camera.release()
