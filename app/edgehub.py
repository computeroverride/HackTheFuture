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
    """
    Publishes ADAM-6717 values to EdgeHub.

    This uses the SCADA device SAS token copied from EdgeHub.
    The Python laptop acts as the data gateway.
    """

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
    def _on_connection_state_change(
        self,
        *args,
        **kwargs,
    ) -> None:
        self.connected = self.client.connected
        if self.connected:
            print("EdgeHub Azure IoT connection established.")
        else:
            print("EdgeHub Azure IoT connection lost.")

    def connect_and_upload_tags(self) -> None:
        """
        Connect to EdgeHub, mark the Python gateway online,
        then create/update all dashboard tags.
        """

        self.client.connect()
        if not self.client.connected:
            raise ConnectionError("Could not connect to EdgeHub using the SCADA SAS token.")

        self.connected = True

        self._send_edgehub_message(
            message_type="conn",
            payload=ConnectMessage().getJson(),
        )

        self._send_protocol_heartbeat(force=True)

        self.upload_tag_configuration()
        print(f"EdgeHub ready. Node ID: {self.settings.edgehub_node_id}")

    def disconnect(self) -> None:
        """Tell EdgeHub the gateway is stopping, then disconnect."""

        try:
            if self.client.connected:
                self._send_edgehub_message("conn", DisconnectMessage().getJson())
                self.client.disconnect()
        except Exception as error:
            print(f"EdgeHub disconnect warning: {error}")
        finally:
            self.connected = False

    # ========================================================
    # MESSAGE TRANSPORT
    # ========================================================
    def _send_edgehub_message(
        self,
        message_type: str,
        payload: str,
    ) -> None:
        """
        EdgeHub protocol message types:

        conn = connect / disconnect / heartbeat
        cfg  = tag configuration
        data = live tag data
        """

        if not self.client.connected:
            raise ConnectionError("EdgeHub is not connected.")

        azure_message = Message(payload)
        azure_message.custom_properties[message_type] = ""
        self.client.send_message(azure_message)

    def _send_protocol_heartbeat(
        self,
        force: bool = False,
    ) -> None:
        """Keep the logical SCADA gateway online in EdgeHub."""

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
        """
        Create/update the ADAM-6717 logical device and tags.
        Safe to call every time the gateway starts.
        """

        edge_config = EdgeConfig()
        node_config = NodeConfig(nodeType=constant.EdgeType["Gateway"])
        device_config = DeviceConfig(
            id=self.settings.edgehub_device_id,
            name="ADAM-6717 Conveyor I/O",
            deviceType="ADAM-6717",
            description=(
                "Python gateway for ADAM-6717 DI, DO and AI data"
            ),
        )

        # ----------------------------------------------------
        # DI2 button
        # ----------------------------------------------------
        device_config.discreteTagList.append(
            DiscreteTagConfig(
                name="di2_button_live",
                description="Current DI2 button state",
                readOnly=True,
                arraySize=0,
                state0="Released",
                state1="Pressed",
                state2=None,
                state3=None,
                state4=None,
                state5=None,
                state6=None,
                state7=None,
            )
        )

        # ----------------------------------------------------
        # DO0 fan relay
        # ----------------------------------------------------
        device_config.discreteTagList.append(
            DiscreteTagConfig(
                name="fan_do0_state",
                description="Current DO0 fan relay state",
                readOnly=True,
                arraySize=0,
                state0="OFF",
                state1="ON",
                state2=None,
                state3=None,
                state4=None,
                state5=None,
                state6=None,
                state7=None,
            )
        )

        # ----------------------------------------------------
        # Button press count
        # ----------------------------------------------------
        device_config.analogTagList.append(
            AnalogTagConfig(
                name="button_press_count",
                description="Number of DI2 button presses since startup",
                readOnly=True,
                arraySize=0,
                spanHigh=100000,
                spanLow=0,
                engineerUnit="presses",
                integerDisplayFormat=0,
                fractionDisplayFormat=0,
            )
        )

        # ----------------------------------------------------
        # Button/fan event text
        # ----------------------------------------------------
        device_config.textTagList.append(
            TextTagConfig(
                name="last_button_event",
                description="Latest DI2 button and DO0 fan action",
                readOnly=True,
                arraySize=0,
            )
        )

        # ----------------------------------------------------
        # AI2 temperature sensor voltage
        # ----------------------------------------------------
        device_config.analogTagList.append(
            AnalogTagConfig(
                name="ai2_temperature_voltage",
                description="AI2 voltage from temperature sensor",
                readOnly=True,
                arraySize=0,
                spanHigh=10,
                spanLow=-10,
                engineerUnit="V",
                integerDisplayFormat=0,
                fractionDisplayFormat=3,
            )
        )

        # ----------------------------------------------------
        # DO1 buzzer
        # ----------------------------------------------------
        device_config.discreteTagList.append(
            DiscreteTagConfig(
                name="buzzer_do1_state",
                description="Current DO1 buzzer state",
                readOnly=True,
                arraySize=0,
                state0="OFF",
                state1="ON",
                state2=None,
                state3=None,
                state4=None,
                state5=None,
                state6=None,
                state7=None,
            )
        )

        # ----------------------------------------------------
        # Temperature alarm
        # ----------------------------------------------------
        device_config.discreteTagList.append(
            DiscreteTagConfig(
                name="temperature_alarm",
                description="Temperature voltage threshold alarm",
                readOnly=True,
                arraySize=0,
                state0="Normal",
                state1="Alarm",
                state2=None,
                state3=None,
                state4=None,
                state5=None,
                state6=None,
                state7=None,
            )
        )

        # ----------------------------------------------------
        # Temperature event text
        # ----------------------------------------------------
        device_config.textTagList.append(
            TextTagConfig(
                name="last_temperature_event",
                description="Latest AI2 and DO1 buzzer action",
                readOnly=True,
                arraySize=0,
            )
        )

        # ----------------------------------------------------
        # Overall system status
        # ----------------------------------------------------
        device_config.textTagList.append(
            TextTagConfig(
                name="system_status",
                description="Overall gateway status",
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
            raise RuntimeError(
                "Could not build EdgeHub tag configuration payload."
            )

        self._send_edgehub_message(
            message_type="cfg",
            payload=payload,
        )

        print(
            "EdgeHub tag configuration sent: "
            "di2_button_live, fan_do0_state, button_press_count, "
            "last_button_event, ai2_temperature_voltage, "
            "buzzer_do1_state, temperature_alarm, "
            "last_temperature_event, system_status"
        )

    # ========================================================
    # DATA HELPERS
    # ========================================================
    def _send_edge_data(
        self,
        edge_data: EdgeData,
    ) -> bool:
        """Convert EdgeData and send it to EdgeHub."""

        self._send_protocol_heartbeat()

        edge_data.timestamp = datetime.now()

        result, payloads = converter.convertData(edge_data)

        if not result:
            print(
                "Could not convert EdgeHub tag data into payload."
            )
            return False

        for payload in payloads:
            self._send_edgehub_message(
                message_type="data",
                payload=payload,
            )

        return True

    # ========================================================
    # LIVE DATA PUBLISHING — BUTTON + FAN
    # ========================================================
    def publish_button_fan(
        self,
        button_pressed: bool,
        fan_on: bool,
        button_press_count: int,
        last_event: str,
    ) -> bool:
        """Upload DI2 button and DO0 fan states."""

        try:
            edge_data = EdgeData()

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "di2_button_live",
                    int(button_pressed),
                )
            )

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "fan_do0_state",
                    int(fan_on),
                )
            )

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "button_press_count",
                    button_press_count,
                )
            )

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "last_button_event",
                    last_event,
                )
            )

            return self._send_edge_data(edge_data)

        except Exception as error:
            print(f"EdgeHub button/fan publish error: {error}")
            return False

    # Backward compatibility with your older service code.
    def publish(
        self,
        button_pressed: bool,
        fan_on: bool,
        button_press_count: int,
        last_event: str,
    ) -> bool:
        return self.publish_button_fan(
            button_pressed=button_pressed,
            fan_on=fan_on,
            button_press_count=button_press_count,
            last_event=last_event,
        )

    # ========================================================
    # LIVE DATA PUBLISHING — TEMPERATURE + BUZZER
    # ========================================================
    def publish_temperature_buzzer(
        self,
        ai2_voltage: float,
        buzzer_on: bool,
        temperature_alarm: bool,
        last_event: str,
        system_status: str,
    ) -> bool:
        """Upload AI2 voltage and DO1 buzzer states."""

        try:
            edge_data = EdgeData()

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "ai2_temperature_voltage",
                    round(ai2_voltage, 3),
                )
            )

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "buzzer_do1_state",
                    int(buzzer_on),
                )
            )

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "temperature_alarm",
                    int(temperature_alarm),
                )
            )

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "last_temperature_event",
                    last_event,
                )
            )

            edge_data.tagList.append(
                EdgeTag(
                    self.settings.edgehub_device_id,
                    "system_status",
                    system_status,
                )
            )

            return self._send_edge_data(edge_data)

        except Exception as error:
            print(f"EdgeHub temperature/buzzer publish error: {error}")
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
