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

3. Configure required environment variables in `.env`.


## Run

```powershell
py main.py
```

## ML / AI

The app uses the `app.ml.training` training script and the `app.ml.pill_inference.PillPredictor` model.

### Image storage

- Pass images are stored under `storage/predictions/pass/`.
- Failed or uncertain images are stored under `storage/failures/`.
- Each saved image file is named using the product ID, predicted label, and timestamp.

### Inspection flow

- The conveyor controller captures a sharpest webcam frame via `app.services.pill_inspector.PillInspector`.
- `PillPredictor.predict_frame()` converts the image to RGB, applies transforms, and runs the model.
- The predicted label, confidence, and final pass/fail decision are returned, then saved to disk.
- If Telegram is enabled, the saved image is sent with feedback buttons.

### Feedback loop

- Telegram feedback is polled continuously by `app.conveyor.inspection.poll_telegram_feedback()`.
- Feedback events are stored in the notifier and parsed into:
  - `feedback_product_id`
  - `actual_class`
  - `feedback_status`
  - `ml_prediction_correct`
- The controller updates totals and status on human feedback.

### Training command

Use the training script to retrain or improve the classifier from image folders:

```powershell
py app\ml\training.py --data storage\datasets --output storage\models\pill_classifier.pt --epochs 20 --batch-size 16
```

## EdgeHub

The app sends a consolidated monitoring snapshot to EdgeHub every 60 seconds.

### What is sent

- Device and workflow state
- Current product and process stage
- Last event and last completed product
- ML classification status, prediction, and confidence
- Feedback status and actual class
- Camera/ADAM connectivity flags
- Reject and buzzer states
- 60-second counters for button, photocell, completion, reject impact, fan, buzzer, and feedback events
- lifetime totals for inspections, passes, fail_defect, fail_different, reject confirmations, reject timeouts, feedback count, and ML corrections
- cycle-time metrics: last and average cycle duration

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
