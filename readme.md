# HackTheFuture ADAM-6717 Gateway

This repository is a Python gateway for the ADAM-6717 I/O device. It reads sensor values, runs ML inspection for pill inspection, reports monitoring data to Azure EdgeHub, and optionally sends results to Telegram.

## Overview

- `main.py` starts the conveyor controller.
- `app/conveyor/` contains the conveyor state machine, inspection orchestration, and EdgeHub reporting.
- `app/settings.py` loads configuration from `.env`.
- `integrations/telegram_notifier.py` handles Telegram notifications and feedback.

## Features

- Button-triggered product registration.
- Camera-based inspection via `app.services.pill_inspector`.
- Reject/fan/buzzer control through ADAM-6717 DO outputs.
- Periodic EdgeHub snapshot publishing.
- Optional Telegram inspection result notification and feedback capture.

## Hardware Mapping

| Function | ADAM Channel | Default Modbus Address |
|---|---|---:|
| Product button | DI2 | `DI2_ADDRESS` |
| Reject fan relay | DO0 | `DO0_ADDRESS` |
| Buzzer | DO2 | `DO2_ADDRESS` |
| Sound reject sensor | AI0 | `AI0_ADDRESS` |
| Camera photocell | AI4 | `AI4_ADDRESS` |

## Setup

1. Create or update `.env` at the repository root.
2. Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

3. Configure required environment variables given in .env-example:



## Run

```powershell
py main.py
```


## Project Structure

- `main.py` — application entrypoint.
- `app/conveyor/controller.py` — conveyor processing loop and hardware orchestration.
- `app/conveyor/helpers.py` — sensor helpers and label normalization.
- `app/conveyor/inspection.py` — inspection and Telegram notification logic.
- `app/conveyor/workflow.py` — workflow state transitions and EdgeHub snapshot building.
- `app/settings.py` — `.env`-based settings loader.
- `app/services/` — hardware service wrappers for ADAM I/O and camera logic.
- `integrations/telegram_notifier.py` — Telegram API integration.

## Notes

- EdgeHub publishing is disabled unless `EDGEHUB_ENABLED=true` and `EDGEHUB_SAS_TOKEN` is valid.
- Telegram notifications are enabled only when `TELEGRAM_ENABLED=true`.
- The app is designed to keep the runtime loop and hardware control separate from the main entrypoint.
