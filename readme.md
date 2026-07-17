# HackTheFuture ADAM-6717 Gateway

This Python gateway runs on the CMIO laptop.

## Workflow

ADAM-6717 -> Python in VS Code -> EdgeHub Dashboard

## Current Features

1. DI2 button toggles DO0 fan relay.
2. AI2 temperature sensor voltage controls DO1 buzzer.
3. Live values are published to EdgeHub tags.

## Hardware Mapping

| Function | ADAM Channel | Modbus Offset |
|---|---:|---:|
| Button | DI2 | 2 |
| Fan relay | DO0 | 16 |
| Temperature voltage | AI2 | 34 |
| Buzzer | DO1 | 17 |

## Setup

Install requirements:

```powershell
py -m pip install -r requirements.txt