from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from app.conveyor.constants import AI_SCAN_ADDRESSES
from app.conveyor.helpers import (
    confidence_percent,
    extract_product_number,
    format_product_id,
    normalise_label,
    read_ai_scan,
    read_sound_voltage,
    refresh_current_outputs,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("good", "good"),
        ("PASS", "good"),
        ("passed", "good"),
        ("different", "fail_different"),
        ("defect", "fail_defect"),
        ("defective", "fail_defect"),
        (None, "unknown"),
    ],
)
def test_normalise_label(raw: object, expected: str) -> None:
    assert normalise_label(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (7, 7),
        ("P007", 7),
        ("PRODUCT-123", 123),
        ("no-number", None),
    ],
)
def test_extract_product_number(
    raw: object,
    expected: int | None,
) -> None:
    assert extract_product_number(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (7, "P007"),
        ("7", "P007"),
        ("P007", "P007"),
        ("PRODUCT-123", "P123"),
        ("manual-id", "manual-id"),
        ("P0004_1737558012", "P0004_1737558012"),
        ("P0004-1737558012", "P1737558012"),
    ],
)
def test_format_product_id(raw: object, expected: str) -> None:
    assert format_product_id(raw) == expected


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.0, 0.0),
        (0.91, 91.0),
        (1.0, 100.0),
        (91.0, 91.0),
    ],
)
def test_confidence_percent(
    confidence: float,
    expected: float,
) -> None:
    assert confidence_percent(confidence) == expected


def test_read_ai_scan_uses_the_required_address_sequence() -> None:
    adam = Mock()
    adam.read_ai_voltage.side_effect = lambda address: address / 10
    settings = SimpleNamespace(ai4_address=38)

    readings = read_ai_scan(adam, settings)

    assert list(readings) == AI_SCAN_ADDRESSES
    assert readings[38] == 3.8
    assert adam.read_ai_voltage.call_args_list == [
        call(address) for address in AI_SCAN_ADDRESSES
    ]


def test_read_sound_voltage_reuses_existing_scan_value() -> None:
    settings = SimpleNamespace(ai0_address=30)
    adam = Mock()

    assert read_sound_voltage(settings, adam, {30: 0.21}) == 0.21
    adam.read_ai_voltage.assert_not_called()


def test_read_sound_voltage_reads_ai0_when_not_in_scan() -> None:
    settings = SimpleNamespace(ai0_address=44)
    adam = Mock()
    adam.read_ai_voltage.return_value = 0.19

    assert read_sound_voltage(settings, adam, {}) == 0.19
    adam.read_ai_voltage.assert_called_once_with(44)
    adam.read_ai_voltage.assert_called_once_with(44)


def test_refresh_current_outputs_updates_and_latches_events() -> None:
    controller = SimpleNamespace(
        adam=Mock(),
        reject_fan_on=False,
        buzzer_on=False,
        window=SimpleNamespace(
            fan_activated=False,
            buzzer_activated=False,
        ),
    )
    controller.adam.read_do0.return_value = True
    controller.adam.read_do2.return_value = True

    refresh_current_outputs(controller)

    assert controller.reject_fan_on is True
    assert controller.buzzer_on is True
    assert controller.window.fan_activated is True
    assert controller.window.buzzer_activated is True
