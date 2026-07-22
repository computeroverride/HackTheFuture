from __future__ import annotations

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.hardware]


def test_adam_connects_and_reads_product_monitoring_inputs() -> None:
    from app.adam import Adam6717Connection
    from app.conveyor.helpers import read_ai_scan
    from app.settings import load_settings

    settings = load_settings()
    adam = Adam6717Connection(settings)

    try:
        adam.connect()
        readings = read_ai_scan(adam, settings)
        crash_sensor = adam.read_di(settings.di0_address)
        entry_button = adam.read_di(settings.di2_address)

        assert settings.ai4_address in readings
        assert isinstance(readings[settings.ai4_address], float)
        assert isinstance(crash_sensor, bool)
        assert isinstance(entry_button, bool)
    finally:
        adam.close()
