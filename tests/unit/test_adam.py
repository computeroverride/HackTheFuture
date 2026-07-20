from __future__ import annotations

import struct

import pytest

from app.adam import Adam6717Connection


pytestmark = pytest.mark.unit


def _cdab_registers(value: float) -> list[int]:
    high_word, low_word = struct.unpack(">HH", struct.pack(">f", value))
    return [low_word, high_word]


@pytest.mark.parametrize("value", [0.0, 0.125, 1.25, -3.5, 9.75])
def test_decode_cdab_float(value: float) -> None:
    adam = Adam6717Connection.__new__(Adam6717Connection)

    decoded = adam._decode_cdab_float(_cdab_registers(value))

    assert decoded == pytest.approx(value)


def test_decode_cdab_float_converts_non_finite_to_zero() -> None:
    adam = Adam6717Connection.__new__(Adam6717Connection)

    assert adam._decode_cdab_float(_cdab_registers(float("inf"))) == 0.0
