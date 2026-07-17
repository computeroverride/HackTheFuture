import time
from datetime import datetime

from azure.iot.device import IoTHubDeviceClient, Message

import edgesync360edgehubedgesdk.Common.Constants as constant
import edgesync360edgehubedgesdk.Common.Converter as converter

from edgesync360edgehubedgesdk.Model.Edge import (
    AnalogTagConfig,
    DeviceConfig,
    DiscreteTagConfig,
    EdgeConfig,
    EdgeData,
    EdgeTag,
    NodeConfig,
    TextTagConfig,
)
from edgesync360edgehubedgesdk.Model.MQTTMessage import (
    ConnectMessage,
    DisconnectMessage,
    HeartbeatMessage,
)

from app.settings import Settings


class EdgeHubPublisher:
    """Publishes conveyor status to EdgeHub through Azure IoT Hub."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = IoTHubDeviceClient.create_from_sastoken(
            settings.edgehub_sas_token
        )
        self.client.on_connection_state_change = self._on_connection_state_change
        self.last_protocol_heartbeat_time = 0.0
        self.connected = False

    # ========================================================
    # CONNECTION
    # ========================================================
    def _on_connection_state_change(self) -> None:
        self.connected = self.client.connected
        if self.connected:
            print("EdgeHub Azure IoT connection established.")
        else:
            print("EdgeHub Azure IoT connection lost.")

    def connect_and_upload_tags(self) -> None:
        self.client.connect()
        if not self.client.connected:
            raise ConnectionError("Could not connect to EdgeHub using the SCADA SAS token.")

        self.connected = True
        self._send_edgehub_message("conn", ConnectMessage().getJson())
        self._send_protocol_heartbeat(force=True)
        self.upload_tag_configuration()
        print(f"EdgeHub ready. Node ID: {self.settings.edgehub_node_id}")

    def disconnect(self) -> None:
        try:
            if self.client.connected:
                self._send_edgehub_message("conn", DisconnectMessage().getJson())
                self.client.disconnect()
        except Exception as error:
            print(f"EdgeHub disconnect warning: {error}")
        finally:
            self.connected = False

    def _send_edgehub_message(self, message_type: str, payload: str) -> None:
        if not self.client.connected:
            raise ConnectionError("EdgeHub is not connected.")
        azure_message = Message(payload)
        azure_message.custom_properties[message_type] = ""
        self.client.send_message(azure_message)

    def _send_protocol_heartbeat(self, force: bool = False) -> None:
        now = time.monotonic()
        heartbeat_due = (
            now - self.last_protocol_heartbeat_time
            >= self.settings.edgehub_protocol_heartbeat_seconds
        )
        if not force and not heartbeat_due:
            return
        self._send_edgehub_message("conn", HeartbeatMessage().getJson())
        self.last_protocol_heartbeat_time = now

    # ========================================================
    # TAG CONFIGURATION
    # ========================================================
    def upload_tag_configuration(self) -> None:
        edge_config = EdgeConfig()
        node_config = NodeConfig(nodeType=constant.EdgeType["Gateway"])
        device_config = DeviceConfig(
            id=self.settings.edgehub_device_id,
            name="ADAM-6717 Conveyor I/O",
            deviceType="ADAM-6717",
            description="Conveyor pill inspection, reject, and safety tags",
        )

        discrete_tags = [
            ("di_camera_sensor", "Camera-area product sensor", "Clear", "Detected"),
            ("di_end_sensor", "End-of-belt verification sensor", "Clear", "Detected"),
            ("di_button", "Physical reset/start button", "Released", "Pressed"),
            ("do_conveyor_motor", "Conveyor motor output", "OFF", "ON"),
            ("alarm_active", "System alarm state", "Normal", "Alarm"),
        ]
        for name, description, state0, state1 in discrete_tags:
            device_config.discreteTagList.append(
                DiscreteTagConfig(
                    name=name,
                    description=description,
                    readOnly=True,
                    arraySize=0,
                    state0=state0,
                    state1=state1,
                    state2=None,
                    state3=None,
                    state4=None,
                    state5=None,
                    state6=None,
                    state7=None,
                )
            )

        analog_tags = [
    ("product_count", "Products detected since startup", 100000, 0, "products", 0),
    ("good_count", "Good products detected since startup", 100000, 0, "products", 0),
    ("faulty_count", "Faulty products detected since startup", 100000, 0, "products", 0),
    ("temperature_c", "Temperature in Celsius", 100, 0, "C", 1),
]
        for name, description, high, low, unit, fraction in analog_tags:
            device_config.analogTagList.append(
                AnalogTagConfig(
                    name=name,
                    description=description,
                    readOnly=True,
                    arraySize=0,
                    spanHigh=high,
                    spanLow=low,
                    engineerUnit=unit,
                    integerDisplayFormat=0,
                    fractionDisplayFormat=fraction,
                )
            )

        text_tags = [
    ("system_state", "State machine status"),
    ("last_event", "Latest useful conveyor event"),
    ("last_result", "Latest ML result"),
    ("queue_summary", "Current queue/status summary"),
]
        for name, description in text_tags:
            device_config.textTagList.append(
                TextTagConfig(
                    name=name,
                    description=description,
                    readOnly=True,
                    arraySize=0,
                )
            )

        node_config.deviceList.append(device_config)
        edge_config.node = node_config

        result, payload = converter.convertCreateorUpdateConfig(
            action=constant.ActionType["Delsert"],
            nodeId=self.settings.edgehub_node_id,
            config=edge_config,
            heartbeat=int(self.settings.edgehub_protocol_heartbeat_seconds),
        )
        if not result:
            raise RuntimeError("Could not build EdgeHub tag configuration payload.")

        self._send_edgehub_message("cfg", payload)
        print("EdgeHub conveyor tag configuration sent.")

    # ========================================================
    # LIVE DATA PUBLISHING
    # ========================================================
    def publish_system_status(
    self,
    system_state: str,
    last_event: str,
    product_count: int,
    good_count: int,
    faulty_count: int,
    last_result: str,
    queue_summary: str,
    alarm_active: bool,
    camera_sensor: bool,
    end_sensor: bool,
    button_pressed: bool,
    conveyor_on: bool,
    temperature_c: float | None,
) -> bool:
        try:
            self._send_protocol_heartbeat()
            edge_data = EdgeData()

            values = {
    "di_camera_sensor": int(camera_sensor),
    "di_end_sensor": int(end_sensor),
    "di_button": int(button_pressed),
    "do_conveyor_motor": int(conveyor_on),
    "alarm_active": int(alarm_active),

    "product_count": product_count,
    "good_count": good_count,
    "faulty_count": faulty_count,
    "temperature_c": -1 if temperature_c is None else round(temperature_c, 1),

    "system_state": system_state,
    "last_event": last_event,
    "last_result": last_result,
    "queue_summary": queue_summary,
}

            for tag_name, value in values.items():
                edge_data.tagList.append(
                    EdgeTag(self.settings.edgehub_device_id, tag_name, value)
                )

            edge_data.timestamp = datetime.now()
            result, payloads = converter.convertData(edge_data)

            if not result:
                print("Could not convert EdgeHub tag data into a payload.")
                return False

            for payload in payloads:
                self._send_edgehub_message("data", payload)
            return True

        except Exception as error:
            print(f"EdgeHub publish error: {error}")
            return False

    # Backward-compatible method for the old ButtonFanService.
    def publish(
        self,
        button_pressed: bool,
        fan_on: bool,
        button_press_count: int,
        last_event: str,
    ) -> bool:
        return self.publish_system_status(
            system_state="LEGACY_BUTTON_FAN",
            last_event=last_event,
            product_count=button_press_count,
            good_count=0,
            faulty_count=0,
            last_result="",
            queue_summary="legacy service",
            alarm_active=False,
            camera_sensor=False,
            end_sensor=False,
            button_pressed=button_pressed,
            conveyor_on=fan_on,
            temperature_c=None,
        )
