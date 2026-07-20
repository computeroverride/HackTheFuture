from __future__ import annotations

import pytest

import app.settings as settings_module


pytestmark = pytest.mark.unit


def test_load_settings_parses_complete_environment(
    configured_environment: dict[str, str],
) -> None:
    settings = settings_module.load_settings()

    assert settings.adam_ip == "10.0.0.1"
    assert settings.adam_port == 5020
    assert settings.di2_address == 2
    assert settings.do0_address == 16
    assert settings.camera_burst_count == 3
    assert settings.telegram_enabled is False
    assert settings.edgehub_enabled is False
    assert settings.edgehub_protocol_heartbeat_seconds == 60


def test_missing_required_setting_raises_clear_error(
    configured_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ADAM_IP")

    with pytest.raises(ValueError, match="ADAM_IP"):
        settings_module.load_settings()


def test_invalid_edgehub_token_disables_edgehub(
    configured_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EDGEHUB_ENABLED", "true")
    monkeypatch.setenv("EDGEHUB_SAS_TOKEN", "not-a-sas-token")

    settings = settings_module.load_settings()

    assert settings.edgehub_enabled is False


def test_valid_edgehub_token_keeps_edgehub_enabled(
    configured_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EDGEHUB_ENABLED", "true")
    monkeypatch.setenv(
        "EDGEHUB_SAS_TOKEN",
        "SharedAccessSignature sr=test&sig=test&se=9999999999",
    )

    settings = settings_module.load_settings()

    assert settings.edgehub_enabled is True
