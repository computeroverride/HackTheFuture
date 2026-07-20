from __future__ import annotations

import importlib

import pytest


pytestmark = pytest.mark.unit


def test_main_module_import_does_not_start_controller() -> None:
    module = importlib.import_module("main")

    assert callable(module.main)
