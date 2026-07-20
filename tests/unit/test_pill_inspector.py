from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest


cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
pytest.importorskip("torch")

from app.services.pill_inspector import PillInspector


pytestmark = pytest.mark.unit


def _make_inspector(
    tmp_path: Path,
    result: dict[str, object],
) -> PillInspector:
    inspector = PillInspector.__new__(PillInspector)
    inspector.predictor = Mock()
    inspector.predictor.predict_frame.return_value = dict(result)
    inspector.failure_dir = tmp_path / "failures"
    inspector.pass_dir = tmp_path / "predictions" / "pass"
    inspector.capture_sharpest_frame = Mock(
        return_value=np.zeros((24, 24, 3), dtype=np.uint8)
    )
    return inspector


def test_inspect_saves_pass_image_for_telegram(tmp_path: Path) -> None:
    inspector = _make_inspector(
        tmp_path,
        {
            "is_pass": True,
            "final_label": "good",
            "confidence": 0.93,
        },
    )

    result = inspector.inspect("P001")

    saved_image = Path(str(result["saved_image"]))
    assert saved_image.exists()
    assert saved_image.parent == inspector.pass_dir
    assert "P001_good" in saved_image.name


def test_inspect_saves_failed_image_in_failure_directory(
    tmp_path: Path,
) -> None:
    inspector = _make_inspector(
        tmp_path,
        {
            "is_pass": False,
            "final_label": "fail_uncertain",
            "confidence": 0.44,
        },
    )

    result = inspector.inspect("P002")

    saved_image = Path(str(result["saved_image"]))
    assert saved_image.exists()
    assert saved_image.parent == inspector.failure_dir
    assert "P002_fail_uncertain" in saved_image.name
