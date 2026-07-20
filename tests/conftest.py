from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest


LIVE_MARKERS = {
    "hardware": "--run-hardware",
    "camera": "--run-camera",
    "edgehub": "--run-edgehub",
    "telegram": "--run-telegram",
}


REQUIRED_ENVIRONMENT = {
    "ADAM_IP": "10.0.0.1",
    "ADAM_PORT": "5020",
    "ADAM_SLAVE_ID": "1",
    "DI0_ADDRESS": "0",
    "DI2_ADDRESS": "2",
    "DO0_ADDRESS": "16",
    "DO2_ADDRESS": "18",
    "AI0_ADDRESS": "30",
    "AI2_ADDRESS": "34",
    "AI4_ADDRESS": "38",
    "AI6_ADDRESS": "42",
    "CAMERA_INDEX": "0",
    "CAMERA_BURST_COUNT": "3",
    "CAMERA_BURST_GAP_SECONDS": "0.15",
    "AI_TEMPERATURE_ADDRESS": "0",
    "TEMPERATURE_ENABLED": "false",
    "POLL_INTERVAL_SECONDS": "0.10",
    "DEBOUNCE_SECONDS": "0.20",
    "PUBLISH_HEARTBEAT_SECONDS": "3.0",
    "BUZZER_ON_VOLTAGE": "2.85",
    "BUZZER_OFF_VOLTAGE": "2.80",
    "TELEGRAM_ENABLED": "false",
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    "TELEGRAM_FEEDBACK_CHAT_ID": "",
    "EDGEHUB_ENABLED": "false",
    "EDGEHUB_NODE_ID": "",
    "EDGEHUB_SAS_TOKEN": "",
    "EDGEHUB_DEVICE_ID": "ADAM6717_IO",
    "EDGEHUB_PROTOCOL_HEARTBEAT_SECONDS": "60",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("live integrations")
    group.addoption(
        "--run-hardware",
        action="store_true",
        default=False,
        help="run live ADAM-6717 tests",
    )
    group.addoption(
        "--run-camera",
        action="store_true",
        default=False,
        help="run live camera tests",
    )
    group.addoption(
        "--run-edgehub",
        action="store_true",
        default=False,
        help="run live EdgeHub tests",
    )
    group.addoption(
        "--run-telegram",
        action="store_true",
        default=False,
        help="run live Telegram tests",
    )
    group.addoption(
        "--run-all-live",
        action="store_true",
        default=False,
        help="run every live integration test",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    run_all = bool(config.getoption("--run-all-live"))

    for marker_name, option_name in LIVE_MARKERS.items():
        enabled = run_all or bool(config.getoption(option_name))
        if enabled:
            continue

        skip_marker = pytest.mark.skip(
            reason=f"requires {option_name}",
        )

        for item in items:
            if marker_name in item.keywords:
                item.add_marker(skip_marker)


@pytest.fixture
def configured_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, str]:
    """Provide a complete, isolated environment for `load_settings()`."""
    import app.settings as settings_module

    monkeypatch.setattr(settings_module, "ENV_PATH", tmp_path / ".env")

    for name, value in REQUIRED_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)

    return dict(REQUIRED_ENVIRONMENT)


@pytest.fixture
def controller_factory() -> Callable[..., Any]:
    """Create a controller-shaped test double for workflow functions."""
    from app.conveyor.workflow import ReportingWindow

    class ControllerStub(SimpleNamespace):
        @property
        def average_cycle_time_seconds(self) -> float:
            if self._finished_cycle_count <= 0:
                return 0.0
            return (
                self._cycle_time_total_seconds
                / self._finished_cycle_count
            )

    def factory(
        *,
        notifier: bool = True,
        edgehub: bool = True,
        inspector: object | None = object(),
    ) -> ControllerStub:
        return ControllerStub(
            fan_relay=Mock(),
            buzzer=Mock(),
            notifier=Mock() if notifier else None,
            edgehub=Mock() if edgehub else None,
            inspector=inspector,
            adam=Mock(),
            adam_connected=True,
            process_state="IDLE",
            current_product_id="",
            current_result=None,
            product_started_at=None,
            reject_started_at=None,
            reject_sound_previous=False,
            last_product_event="System started",
            last_completed_product_id="",
            product_at_camera_now=False,
            completion_sensor_active_now=False,
            reject_fan_on=False,
            buzzer_on=False,
            classification_status="PENDING",
            ml_prediction="",
            ml_confidence_percent=0.0,
            feedback_product_id="",
            feedback_status="Pending",
            actual_class="",
            feedback_received=False,
            ml_prediction_correct=False,
            alarm_active=False,
            last_alarm_message="",
            last_reject_confirmed=False,
            inspection_count_total=0,
            good_count_total=0,
            fail_defect_count_total=0,
            fail_different_count_total=0,
            reject_confirmed_total=0,
            reject_timeout_total=0,
            feedback_count_total=0,
            ml_correction_count_total=0,
            last_cycle_time_seconds=0.0,
            _cycle_time_total_seconds=0.0,
            _finished_cycle_count=0,
            window=ReportingWindow(),
            _last_edgehub_window_started_at=100.0,
            _last_feedback_poll=100.0,
        )

    return factory
