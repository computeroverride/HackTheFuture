import os
import subprocess
import sys
from pathlib import Path


def test_test_services_one_by_one_no_module_not_found_error() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        {
            "ADAM_IP": "127.0.0.1",
            "ADAM_PORT": "5020",
            "ADAM_SLAVE_ID": "1",
            "DI0_ADDRESS": "0",
            "DI2_ADDRESS": "2",
            "DO0_ADDRESS": "0",
            "DO2_ADDRESS": "2",
            "AI0_ADDRESS": "30",
            "AI2_ADDRESS": "34",
            "AI4_ADDRESS": "38",
            "AI6_ADDRESS": "0",
            "CAMERA_INDEX": "0",
            "CAMERA_BURST_COUNT": "3",
            "CAMERA_BURST_GAP_SECONDS": "0.15",
            "AI_TEMPERATURE_ADDRESS": "0",
            "TEMPERATURE_ENABLED": "false",
            "POLL_INTERVAL_SECONDS": "0.05",
            "DEBOUNCE_SECONDS": "0.20",
            "PUBLISH_HEARTBEAT_SECONDS": "3.0",
            "BUZZER_ON_VOLTAGE": "2.85",
            "BUZZER_OFF_VOLTAGE": "2.80",
            "EDGEHUB_ENABLED": "false",
            "EDGEHUB_NODE_ID": "",
            "EDGEHUB_SAS_TOKEN": "",
            "EDGEHUB_DEVICE_ID": "ADAM6717_IO",
            "EDGEHUB_PROTOCOL_HEARTBEAT_SECONDS": "60",
        }
    )

    completed = subprocess.run(
        [sys.executable, "tests/test_services_one_by_one.py"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    output = completed.stdout + completed.stderr
    assert "ModuleNotFoundError: No module named 'app'" not in output
