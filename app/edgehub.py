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
    Publishes EdgeHub SCADA protocol messages through Azure IoT Hub.

    The SCADA device's SAS token is used directly.
    This avoids requiring an Azure SharedAccessKey connection string.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        self.client = IoTHubDeviceClient.create_from_sastoken(
            settings.edgehub_sas_token
        )

        self.client.on_connection_state_change = (
            self._on_connection_state_change
        )

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
        """
        Connect to the SCADA node, mark it online,
        then create/update all dashboard tags.
        """
        self.client.connect()

        if not self.client.connected:
            raise ConnectionError(
                "Could not connect to EdgeHub using the SCADA SAS token."
            )

        self.connected = True

        # Tell EdgeHub that this Python SCADA gateway is online.
        self._send_edgehub_message(
            message_type="conn",
            payload=ConnectMessage().getJson(),
        )

        self._send_protocol_heartbeat(force=True)

        # Creates tags on first run; updates them safely later.
        self.upload_tag_configuration()

        print(
            "EdgeHub ready. "
            f"Node ID: {self.settings.edgehub_node_id}"
        )

    def disconnect(self) -> None:
        """Tell EdgeHub the gateway is stopping, then disconnect."""
        try:
            if self.client.connected:
                self._send_edgehub_message(
                    message_type="conn",
                    payload=DisconnectMessage().getJson(),
                )

                self.client.disconnect()

        except Exception as error:
            print(f"EdgeHub disconnect warning: {error}")

        finally:
            self.connected = False

    # ========================================================
    # EDGEBHUB MESSAGE TRANSPORT
    # ========================================================
    def _send_edgehub_message(
        self,
        message_type: str,
        payload: str,
    ) -> None:
        """
        EdgeHub's Azure transport identifies the intended
        WISE-PaaS / EdgeHub protocol channel through a
        custom message property:

        conn = connection / heartbeat
        cfg  = tag and device configuration
        data = sensor and output values
        """
        if not self.client.connected:
            raise ConnectionError(
                "EdgeHub is not connected."
            )

        azure_message = Message(payload)

        # This matches the EdgeHub SDK Azure transport style.
        azure_message.custom_properties[message_type] = ""

        self.client.send_message(azure_message)

    def _send_protocol_heartbeat(
        self,
        force: bool = False,
    ) -> None:
        """
        Keeps the logical SCADA gateway marked online in EdgeHub.
        """
        now = time.monotonic()

        heartbeat_due = (
            now - self.last_protocol_heartbeat_time
            >= self.settings.edgehub_protocol_heartbeat_seconds
        )

        if not force and not heartbeat_due:
            return

        self._send_edgehub_message(
            message_type="conn",
            payload=HeartbeatMessage().getJson(),
        )

        self.last_protocol_heartbeat_time = now

    # ========================================================
    # TAG CONFIGURATION
    # ========================================================
    def upload_tag_configuration(self) -> None:
        """
        Create or update the logical ADAM device and its tags.

        This is safe to call every time the program starts.
        """
        edge_config = EdgeConfig()

        node_config = NodeConfig(
            nodeType=constant.EdgeType["Gateway"]
        )

        device_config = DeviceConfig(
            id=self.settings.edgehub_device_id,
            name="ADAM-6717 I/O",
            deviceType="ADAM-6717",
            description=(
                "Live DI2 button state and DO0 fan relay state"
            ),
        )

        # ----------------------------------------------------
        # DI2: physical button state
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
        # DO0: actual relay/fan state
        # ----------------------------------------------------
        device_config.discreteTagList.append(
            DiscreteTagConfig(
                name="fan_do0_state",
                description="Current DO0 relay and fan state",
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
        # Count of DI2 presses since Python started
        # ----------------------------------------------------
        device_config.analogTagList.append(
            AnalogTagConfig(
                name="button_press_count",
                description=(
                    "Number of DI2 button presses "
                    "since the Python gateway started"
                ),
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
        # Human-readable latest action
        # ----------------------------------------------------
        device_config.textTagList.append(
            TextTagConfig(
                name="last_event",
                description="Latest DI2 and fan action",
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
            heartbeat=int(
                self.settings.edgehub_protocol_heartbeat_seconds
            ),
        )

        if not result:
            raise RuntimeError(
                "Could not build the EdgeHub tag configuration payload."
            )

        self._send_edgehub_message(
            message_type="cfg",
            payload=payload,
        )

        print(
            "EdgeHub tag configuration sent: "
            "di2_button_live, fan_do0_state, "
            "button_press_count, last_event"
        )

    # ========================================================
    # LIVE DATA PUBLISHING
    # ========================================================
    def publish(
        self,
        button_pressed: bool,
        fan_on: bool,
        button_press_count: int,
        last_event: str,
    ) -> bool:
        """
        Upload the latest ADAM states to the EdgeHub tags.
        """
        try:
            self._send_protocol_heartbeat()

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
                    "last_event",
                    last_event,
                )
            )

            edge_data.timestamp = datetime.now()

            result, payloads = converter.convertData(edge_data)

            if not result:
                print(
                    "Could not convert the EdgeHub "
                    "tag data into a payload."
                )
                return False

            for payload in payloads:
                self._send_edgehub_message(
                    message_type="data",
                    payload=payload,
                )

            return True

        except Exception as error:
            print(f"EdgeHub publish error: {error}")
            return False