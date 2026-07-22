from __future__ import annotations

AI_SCAN_ADDRESSES = [30, 32, 34, 36, 38, 40, 42]

# Measured: clear ~0.12-0.14 V, covered ~0.07-0.10 V. Threshold sits in
# the gap between the two so noise near either edge doesn't flip it.
PHOTOCELL_THRESHOLD_VOLTAGE = 0.1100
PHOTOCELL_REARM_SECONDS = 2.0

# Reject-bin impact is only confirmed after the sound sensor rises above
# the high threshold (loud impact) and then settles back below the low
# threshold (quiet again) - a rise alone is not enough.
REJECT_SOUND_HIGH_THRESHOLD_VOLTAGE = 0.1300
REJECT_SOUND_LOW_THRESHOLD_VOLTAGE = 0.0500

# How long the reject fan/relay stays on before the sound sensor starts
# listening for the reject-bin impact.
REJECT_FAN_PULSE_SECONDS = 3.0

# How long to listen (after the fan pulse ends) for the sound sensor to
# rise above HIGH and settle back below LOW before raising a timeout alarm.
REJECT_CONFIRM_TIMEOUT_SECONDS = 20.0
EDGEHUB_REPORTING_INTERVAL_SECONDS = 60.0
