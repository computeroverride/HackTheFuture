from __future__ import annotations

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.edgehub]


def test_edgehub_accepts_one_product_monitoring_snapshot() -> None:
    from app.edgehub import EdgeHubPublisher
    from app.settings import load_settings

    settings = load_settings()
    if not settings.edgehub_enabled:
        pytest.skip("EDGEHUB_ENABLED is false or its SAS token is invalid")

    publisher = EdgeHubPublisher(settings)

    snapshot = {
        "adam_connected": True,
        "camera_available": True,
        "product_in_progress": True,
        "current_product_id": "P999",
        "process_state": "INSPECTING",
        "last_product_event": "pytest live snapshot",
        "classification_status": "PENDING",
        "ml_prediction": "",
        "ml_confidence_percent": 0.0,
        "button_triggered_60s": True,
        "products_started_60s": 1,
    }

    try:
        publisher.connect_and_upload_tags()
        due_time = (
            publisher._last_data_publish_time
            + publisher.reporting_interval_seconds
        )

        assert publisher.publish_monitoring_snapshot(
            snapshot=snapshot,
            now=due_time,
        ) is True
    finally:
        publisher.disconnect()
