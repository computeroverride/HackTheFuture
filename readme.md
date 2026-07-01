## First-time setup

### Install packages

Open PowerShell in the project root:

```powershell
py -m pip install -r requirements.txt
```

### Create local settings

Copy `.env.example` and rename the copy to `.env`.

```text
.env              → private gateway settings; never commit
.env.example      → placeholders only; commit this
```

### Running the system

```powershell
py main.py
```

Stop with:

```text
Ctrl + C
```

---
# How to create a new sensor or feature

Every new feature goes inside:

```text
app/services/
```

Each service must use this pattern:

```python
start()
tick(now)
```

- `start()` runs once at gateway startup.
- `tick(now)` runs once per central loop cycle.
- `tick()` should be quick.
- Never place `while True` inside a service.

---

## Service template

```python
from app.adam import Adam6717Connection
from app.edgehub import EdgeHubPublisher
from app.settings import Settings


class ExampleService:
    def __init__(
        self,
        settings: Settings,
        adam: Adam6717Connection,
        edgehub: EdgeHubPublisher | None,
    ):
        self.settings = settings
        self.adam = adam
        self.edgehub = edgehub

        self.last_covered_state = None

    def start(self) -> None:
        print("Example service started.")

    def tick(self, now: float) -> None:
        # 1. Read the sensor once.
        # sensor_value = self.adam.read_photocell()

        # 2. Apply feature logic.
        # covered = sensor_value == 0

        # 3. Publish only when the useful state changes.
        # if covered != self.last_covered_state:
        #     self.edgehub.publish_photocell(...)
        #     self.last_covered_state = covered
        pass
```

---

## Register a new service in `main.py`

### 1. Import it

```python
from app.services.example import ExampleService
```

### 2. Create it

```python
Example_service = ExampleService(
    settings=settings,
    adam=adam,
    edgehub=edgehub,
)
```

### 3. Add it to the shared service list

```python
services = [
    example_service1,
    example_service2,
     example_service3,
]
```

`main.py` will then call each service:

```python
for service in services:
    service.start()

while True:
    now = time.monotonic()

    for service in services:
        service.tick(now)

    time.sleep(settings.poll_interval_seconds)
```

This lets multiple sensors run without blocking each other.

---

## Add a new ADAM I/O helper

Do not put raw Modbus addresses throughout feature files.

Add clear helpers in `app/adam.py`, for example:

```python
def read_photocell(self) -> bool:
    result = self.client.read_coils(
        address=self.settings.example_address,
        count=1,
        device_id=self.settings.adam_slave_id,
    )

    if result.isError():
        raise RuntimeError(f"Could not read sensor: {result}")

    return bool(result.bits[0])
```

Then add the physical address in:

1. the real gateway `.env`
2. `Settings` in `app/settings.py`

---

## Add a new EdgeHub tag

When a feature needs to display data:

1. Define the tag in `app/edgehub.py`.
2. Send its value from the relevant service.
3. Run `py main.py` once so EdgeHub receives the tag definition.
4. Confirm the value appears in **CMIO-Gateway → Tags**.
5. Add a dashboard panel for it.

Use descriptive `snake_case` names.

## Dashboard workflow

Before creating a dashboard panel, confirm the tag has a live value:

```text
EdgeHub → Device Management → CMIO-Gateway → Tags
```

Then open the dashboard and configure the panel:

```text
Datasource: EdgeHub-SimpleJson
Source: EdgeHub-device-management
Device: CMIO-Gateway
Tag: <your_tag_name>
TagProperty: Value
DataType: RT
```

---