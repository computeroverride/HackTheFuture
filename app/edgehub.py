from __future__ import annotations

import time
from datetime import datetime
from typing import Any

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


EDGEHUB_REPORTING_INTERVAL_SECONDS = 60.0


class EdgeHubPublisher:


    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = IoTHubDeviceClient.create_from_sastoken(
            settings.edgehub_sas_token
        )
        self.client.on_connection_state_change = (
            self._on_connection_state_change
        )

        self.connected = False
        self._previous_connected_state: bool | None = None
        self._last_protocol_heartbeat_time = 0.0

        # Set when the connection is established. This prevents a data
        # snapshot from being sent immediately at startup; the first data
        # snapshot is due only after the full configured interval.
        self._last_data_publish_time = 0.0

   
    # Connection and transport
   

    @property
    def reporting_interval_seconds(self) -> float:
        return EDGEHUB_REPORTING_INTERVAL_SECONDS

    def _on_connection_state_change(
        self,
        *args: object,
        **kwargs: object,
    ) -> None:
        del args, kwargs

        new_state = bool(self.client.connected)

        if (
            self._previous_connected_state is None
            or new_state != self._previous_connected_state
        ):
            self.connected = new_state
            print(
                "EdgeHub Azure IoT connection established."
                if new_state
                else "EdgeHub Azure IoT connection lost."
            )
            self._previous_connected_state = new_state

    def connect_and_upload_tags(self) -> None:
        self.client.connect()

        if not self.client.connected:
            raise ConnectionError(
                "Could not connect to EdgeHub using the SCADA SAS token."
            )

        self.connected = True

        self._send_edgehub_message(
            message_type="conn",
            payload=ConnectMessage().getJson(),
        )
        self._send_protocol_heartbeat(force=True)
        self.upload_tag_configuration()

        # Start the 60-second data interval after connection/configuration.
        self._last_data_publish_time = time.monotonic()

        print(
            "EdgeHub ready. "
            f"Node ID: {self.settings.edgehub_node_id}"
        )
        print(
            "EdgeHub product data interval: "
            f"{self.reporting_interval_seconds:.0f} seconds."
        )

    def disconnect(self) -> None:
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

    def _send_edgehub_message(
        self,
        message_type: str,
        payload: str,
    ) -> None:
        if not self.client.connected:
            raise ConnectionError("EdgeHub is not connected.")

        message = Message(payload)
        message.custom_properties[message_type] = ""
        self.client.send_message(message)

    def _send_protocol_heartbeat(
        self,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        heartbeat_due = (
            now - self._last_protocol_heartbeat_time
            >= self.reporting_interval_seconds
        )

        if not force and not heartbeat_due:
            return

        self._send_edgehub_message(
            message_type="conn",
            payload=HeartbeatMessage().getJson(),
        )
        self._last_protocol_heartbeat_time = now

    def data_publish_due(
        self,
        now: float | None = None,
    ) -> bool:
        if now is None:
            now = time.monotonic()

        return (
            now - self._last_data_publish_time
            >= self.reporting_interval_seconds
        )

   
    # Tag configuration helpers
   

    @staticmethod
    def _add_text_tag(
        device: DeviceConfig,
        name: str,
        description: str,
    ) -> None:
        device.textTagList.append(
            TextTagConfig(
                name=name,
                description=description,
                readOnly=True,
                arraySize=0,
            )
        )

    @staticmethod
    def _add_boolean_tag(
        device: DeviceConfig,
        name: str,
        description: str,
        state0: str,
        state1: str,
    ) -> None:
        device.discreteTagList.append(
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

    @staticmethod
    def _add_number_tag(
        device: DeviceConfig,
        name: str,
        description: str,
        span_low: float,
        span_high: float,
        unit: str,
        fraction_digits: int = 0,
    ) -> None:
        device.analogTagList.append(
            AnalogTagConfig(
                name=name,
                description=description,
                readOnly=True,
                arraySize=0,
                spanHigh=span_high,
                spanLow=span_low,
                engineerUnit=unit,
                integerDisplayFormat=0,
                fractionDisplayFormat=fraction_digits,
            )
        )

    def upload_tag_configuration(self) -> None:
      
        edge_config = EdgeConfig()
        node_config = NodeConfig(
            nodeType=constant.EdgeType["Gateway"]
        )
        device = DeviceConfig(
            id=self.settings.edgehub_device_id,
            name="CMIO Product Monitoring",
            deviceType="ADAM-6717 + Vision",
            description=(
                "End-user product flow, inspection, rejection and "
                "completion monitoring. Updated once per minute."
            ),
        )

        # -------------------------------
        # System and active product
        # -------------------------------
        self._add_boolean_tag(
            device,
            "adam_connected",
            "Whether the ADAM-6717 gateway is connected",
            "Disconnected",
            "Connected",
        )
        self._add_boolean_tag(
            device,
            "camera_available",
            "Whether the vision inspection service is available",
            "Unavailable",
            "Available",
        )
        self._add_boolean_tag(
            device,
            "product_in_progress",
            "Whether a product is currently being processed",
            "No product",
            "In progress",
        )
        self._add_text_tag(
            device,
            "current_product_id",
            "Identifier of the product currently in progress",
        )
        self._add_text_tag(
            device,
            "process_state",
            "Current stage of the product workflow",
        )
        self._add_text_tag(
            device,
            "last_product_event",
            "Most recent product-flow event",
        )
        self._add_text_tag(
            device,
            "last_completed_product_id",
            "Most recently completed or rejected product",
        )

        # -------------------------------
        # Inspection and human feedback
        # -------------------------------
        self._add_text_tag(
            device,
            "classification_status",
            "Current or latest GOOD, BAD or PENDING status",
        )
        self._add_text_tag(
            device,
            "ml_prediction",
            "Current or latest ML predicted class",
        )
        self._add_number_tag(
            device,
            "ml_confidence_percent",
            "Current or latest ML confidence",
            0,
            100,
            "%",
            fraction_digits=1,
        )
        self._add_text_tag(
            device,
            "feedback_product_id",
            "Product ID for the latest Telegram feedback",
        )
        self._add_text_tag(
            device,
            "feedback_status",
            "Latest feedback state: Pending, Correct or Incorrect",
        )
        self._add_text_tag(
            device,
            "actual_class",
            "Latest human-confirmed product class",
        )
        self._add_boolean_tag(
            device,
            "feedback_received",
            "Whether feedback has been received for the latest feedback product",
            "Pending",
            "Received",
        )
        self._add_boolean_tag(
            device,
            "ml_prediction_correct",
            "Whether the latest human-confirmed prediction was correct",
            "Incorrect",
            "Correct",
        )

        # -------------------------------
        # Current sensors and actuators
        # -------------------------------
        self._add_boolean_tag(
            device,
            "product_at_camera_now",
            "Whether the photocell currently detects a product at the camera",
            "Clear",
            "Detected",
        )
        self._add_boolean_tag(
            device,
            "completion_sensor_active_now",
            "Whether the completion crash sensor is currently active",
            "Clear",
            "Active",
        )
        self._add_boolean_tag(
            device,
            "reject_fan_on",
            "Current DO0 reject-fan relay state",
            "OFF",
            "ON",
        )
        self._add_boolean_tag(
            device,
            "buzzer_on",
            "Current DO2 buzzer state",
            "Silent",
            "Active",
        )
        self._add_boolean_tag(
            device,
            "alarm_active",
            "Whether a product-monitoring alarm is active",
            "Normal",
            "Alarm",
        )
        self._add_text_tag(
            device,
            "last_alarm_message",
            "Latest product-monitoring alarm message",
        )
        self._add_boolean_tag(
            device,
            "last_reject_confirmed",
            "Whether the most recent rejection was confirmed",
            "Not confirmed",
            "Confirmed",
        )

        # -------------------------------
        # Events observed in the last 60-second window
        # -------------------------------
        window_boolean_tags = (
            (
                "button_triggered_60s",
                "Entry button was triggered during the reporting window",
            ),
            (
                "photocell_triggered_60s",
                "Camera photocell was triggered during the reporting window",
            ),
            (
                "completion_detected_60s",
                "Good-product completion was detected during the reporting window",
            ),
            (
                "reject_impact_detected_60s",
                "Reject-bin impact was detected during the reporting window",
            ),
            (
                "fan_activated_60s",
                "Reject fan was activated during the reporting window",
            ),
            (
                "buzzer_activated_60s",
                "Buzzer was activated during the reporting window",
            ),
        )

        for name, description in window_boolean_tags:
            self._add_boolean_tag(
                device,
                name,
                description,
                "No",
                "Yes",
            )

        # -------------------------------
        # Per-minute and total production counters
        # -------------------------------
        per_minute_number_tags = (
            ("products_started_60s", "Products started in the last reporting window"),
            ("products_inspected_60s", "Products inspected in the last reporting window"),
            ("products_completed_60s", "Good products completed in the last reporting window"),
            ("products_rejected_60s", "Products with confirmed rejection in the last reporting window"),
            ("reject_timeouts_60s", "Unconfirmed reject attempts in the last reporting window"),
            ("feedback_count_60s", "Human feedback responses in the last reporting window"),
        )

        for name, description in per_minute_number_tags:
            self._add_number_tag(
                device,
                name,
                description,
                0,
                100000,
                "products",
            )

        total_number_tags = (
            ("inspection_count_total", "Products inspected since gateway startup"),
            ("good_count_total", "Products predicted good since gateway startup"),
            ("fail_defect_count_total", "Products predicted defective since gateway startup"),
            ("fail_different_count_total", "Products predicted different since gateway startup"),
            ("reject_confirmed_total", "Confirmed rejections since gateway startup"),
            ("reject_timeout_total", "Reject confirmation failures since gateway startup"),
            ("feedback_count_total", "Human feedback responses since gateway startup"),
            ("ml_correction_count_total", "Human feedback corrections since gateway startup"),
        )

        for name, description in total_number_tags:
            self._add_number_tag(
                device,
                name,
                description,
                0,
                1000000,
                "products",
            )

        self._add_number_tag(
            device,
            "last_cycle_time_seconds",
            "Cycle time of the most recently finished product",
            0,
            86400,
            "s",
            fraction_digits=1,
        )
        self._add_number_tag(
            device,
            "average_cycle_time_seconds",
            "Average completed-product cycle time since startup",
            0,
            86400,
            "s",
            fraction_digits=1,
        )

        node_config.deviceList.append(device)
        edge_config.node = node_config

        result, payload = converter.convertCreateorUpdateConfig(
            action=constant.ActionType["Delsert"],
            nodeId=self.settings.edgehub_node_id,
            config=edge_config,
            heartbeat=int(self.reporting_interval_seconds),
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
            "EdgeHub product-monitoring tag configuration sent."
        )

   
    # One consolidated 60-second snapshot
   

    def publish_monitoring_snapshot(
        self,
        snapshot: dict[str, Any],
        now: float | None = None,
    ) -> bool:
       
        if now is None:
            now = time.monotonic()

        if not self.data_publish_due(now):
            return False

        if not self.client.connected:
            print("EdgeHub snapshot skipped: client is disconnected.")
            return False

        try:
            self._send_protocol_heartbeat()

            edge_data = EdgeData()
            edge_data.timestamp = datetime.now()

            text_tags = (
                "current_product_id",
                "process_state",
                "last_product_event",
                "last_completed_product_id",
                "classification_status",
                "ml_prediction",
                "feedback_product_id",
                "feedback_status",
                "actual_class",
                "last_alarm_message",
            )

            boolean_tags = (
                "adam_connected",
                "camera_available",
                "product_in_progress",
                "feedback_received",
                "ml_prediction_correct",
                "product_at_camera_now",
                "completion_sensor_active_now",
                "reject_fan_on",
                "buzzer_on",
                "alarm_active",
                "last_reject_confirmed",
                "button_triggered_60s",
                "photocell_triggered_60s",
                "completion_detected_60s",
                "reject_impact_detected_60s",
                "fan_activated_60s",
                "buzzer_activated_60s",
            )

            number_tags = (
                "ml_confidence_percent",
                "products_started_60s",
                "products_inspected_60s",
                "products_completed_60s",
                "products_rejected_60s",
                "reject_timeouts_60s",
                "feedback_count_60s",
                "inspection_count_total",
                "good_count_total",
                "fail_defect_count_total",
                "fail_different_count_total",
                "reject_confirmed_total",
                "reject_timeout_total",
                "feedback_count_total",
                "ml_correction_count_total",
                "last_cycle_time_seconds",
                "average_cycle_time_seconds",
            )

            for tag_name in text_tags:
                edge_data.tagList.append(
                    EdgeTag(
                        self.settings.edgehub_device_id,
                        tag_name,
                        str(snapshot.get(tag_name, "")),
                    )
                )

            for tag_name in boolean_tags:
                edge_data.tagList.append(
                    EdgeTag(
                        self.settings.edgehub_device_id,
                        tag_name,
                        int(bool(snapshot.get(tag_name, False))),
                    )
                )

            for tag_name in number_tags:
                value = snapshot.get(tag_name, 0)

                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    numeric_value = 0.0

                edge_data.tagList.append(
                    EdgeTag(
                        self.settings.edgehub_device_id,
                        tag_name,
                        numeric_value,
                    )
                )

            result, payloads = converter.convertData(edge_data)

            if not result:
                print(
                    "Could not convert the EdgeHub monitoring snapshot."
                )
                return False

            for payload in payloads:
                self._send_edgehub_message(
                    message_type="data",
                    payload=payload,
                )

            self._last_data_publish_time = now

            print(
                "EdgeHub 60-second monitoring snapshot sent -> "
                f"state={snapshot.get('process_state')}, "
                f"product={snapshot.get('current_product_id') or 'none'}, "
                f"started={snapshot.get('products_started_60s', 0)}, "
                f"inspected={snapshot.get('products_inspected_60s', 0)}, "
                f"completed={snapshot.get('products_completed_60s', 0)}, "
                f"rejected={snapshot.get('products_rejected_60s', 0)}"
            )
            return True

        except Exception as error:
            print(f"EdgeHub snapshot publish error: {error}")
            return False