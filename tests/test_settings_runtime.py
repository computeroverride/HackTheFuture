import app.settings as settings_module


def test_load_settings_uses_safe_defaults_when_env_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_module, "ENV_PATH", tmp_path / ".env")

    for name in [
        "ADAM_IP",
        "ADAM_PORT",
        "ADAM_SLAVE_ID",
        "DI2_ADDRESS",
        "DO0_ADDRESS",
        "DO1_ADDRESS",
        "DO2_ADDRESS",
        "AI2_ADDRESS",
        "EDGEHUB_ENABLED",
        "EDGEHUB_SAS_TOKEN",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = settings_module.load_settings()

    assert settings.adam_ip == "10.0.0.1"
    assert settings.adam_port == 5020
    assert settings.di2_address == 2
    assert settings.do0_address == 16
    assert settings.edgehub_enabled is False
