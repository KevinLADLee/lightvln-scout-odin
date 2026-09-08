"""ROS 2 adapter and command arbiter for a Scout base driver."""

from __future__ import annotations

import contextlib
import math
import threading
import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import Twist, TwistStamped
from rcl_interfaces.msg import ParameterDescriptor, SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from scout_msgs.msg import ScoutStatus
from std_msgs.msg import Bool, String
from std_srvs.srv import SetBool, Trigger

from .safety import select_command
from .telemetry import ScoutTelemetry


def build_diagnostic_status(
    *,
    connected: bool,
    source: str,
    emergency: bool,
    hardware_output_enabled: bool,
    telemetry: dict[str, str] | None = None,
) -> DiagnosticStatus:
    """Build the status consumed by the standard ``vln_web`` robot adapter."""
    status = DiagnosticStatus()
    status.name = "robot_adapter"
    status.hardware_id = "scout"
    if emergency:
        status.level = DiagnosticStatus.ERROR
        status.message = "emergency stop latched"
    elif not connected:
        status.level = DiagnosticStatus.WARN
        status.message = "waiting for Scout /cmd_vel subscriber"
    elif telemetry and telemetry.get("error_code", "0") != "0":
        status.level = DiagnosticStatus.ERROR
        status.message = "Scout reports a base fault"
    elif not hardware_output_enabled:
        status.level = DiagnosticStatus.WARN
        status.message = "connected; hardware output locked"
    elif telemetry and telemetry.get("telemetry_fresh") == "false":
        status.level = DiagnosticStatus.WARN
        status.message = "command subscriber connected; Scout telemetry unavailable"
    else:
        status.level = DiagnosticStatus.OK
        status.message = "ready"
    status.values = [
        KeyValue(key="adapter", value="scout_ros2"),
        KeyValue(key="connected", value=str(connected).lower()),
        KeyValue(key="robot_id", value="scout"),
        KeyValue(key="mode", value="WALK" if connected else "UNKNOWN"),
        KeyValue(key="battery", value=""),
        KeyValue(key="imu", value="UNKNOWN"),
        KeyValue(key="motor", value="UNKNOWN"),
        KeyValue(key="control_source", value=source),
        KeyValue(
            key="supported_actions",
            value="emergency_stop,reset_emergency_stop",
        ),
        KeyValue(key="emergency_stopped", value=str(emergency).lower()),
        KeyValue(
            key="hardware_output_enabled",
            value=str(hardware_output_enabled).lower(),
        ),
    ]
    status.values.extend(
        KeyValue(key=key, value=value) for key, value in (telemetry or {}).items()
    )
    return status


class ScoutAdapterNode(Node):
    """Own manual/auto arbitration, watchdogs, and the final ``/cmd_vel``."""

    def __init__(self) -> None:
        super().__init__("scout_adapter")
        self._declare_parameters()
        self._control_rate_hz = float(self.get_parameter("control_rate_hz").value)
        self._watchdog_s = float(self.get_parameter("input_watchdog_s").value)
        self._max_linear = float(self.get_parameter("max_linear_speed").value)
        self._max_angular = float(self.get_parameter("max_angular_speed").value)
        self._hard_max_linear = self._max_linear
        self._hard_max_angular = self._max_angular
        self._hardware_output_enabled = bool(
            self.get_parameter("hardware_output_enabled").value
        )
        self._require_output_subscriber = bool(
            self.get_parameter("require_output_subscriber").value
        )
        self._telemetry = ScoutTelemetry(
            float(self.get_parameter("status_timeout_s").value)
        )
        if not all(
            math.isfinite(value) and value > 0.0
            for value in (
                self._control_rate_hz, self._watchdog_s,
                self._max_linear, self._max_angular,
            )
        ):
            raise ValueError("invalid Scout adapter limits")

        latched = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._output_pub = self.create_publisher(
            Twist, str(self.get_parameter("output_topic").value), 10
        )
        self._sent_pub = self.create_publisher(
            TwistStamped, str(self.get_parameter("sent_command_topic").value), 20
        )
        self._source_pub = self.create_publisher(String, "control/source", latched)
        self._diagnostics_pub = self.create_publisher(DiagnosticArray, "diagnostics", 10)
        self._event_pub = self.create_publisher(String, "robot/events", 20)
        self.create_subscription(
            ScoutStatus, str(self.get_parameter("status_topic").value),
            self._on_scout_status, 1,
        )
        self.create_subscription(TwistStamped, "web/cmd_vel", self._on_manual, 1)
        self.create_subscription(TwistStamped, "mpc/cmd_vel", self._on_auto, 1)
        self.create_subscription(
            Bool,
            str(self.get_parameter("emergency_stop_topic").value),
            self._on_emergency_stop,
            10,
        )
        self.create_service(SetBool, "control/set_manual", self._set_manual)
        self.create_service(SetBool, "control/set_auto", self._set_auto)
        self.create_service(Trigger, "control/stop", self._stop)
        self.create_service(Trigger, "robot/stand", self._unsupported_mode)
        self.create_service(Trigger, "robot/walk", self._walk_mode)
        self.create_service(Trigger, "robot/sit", self._unsupported_mode)
        self.create_service(Trigger, "robot/toggle_policy", self._unsupported_mode)
        self.create_service(Trigger, "robot/emergency_stop", self._emergency_service)

        self.create_service(
            Trigger, "robot/reset_emergency_stop", self._reset_emergency_service
        )

        self._lock = threading.Lock()
        self._source = "disabled"
        self._manual_command = (0.0, 0.0)
        self._auto_command = (0.0, 0.0)
        self._manual_received_s = float("-inf")
        self._auto_received_s = float("-inf")
        self._emergency_stopped = False
        self._external_emergency = False
        self._closed = False
        self.add_on_set_parameters_callback(self._on_set_parameters)
        self.create_timer(1.0 / self._control_rate_hz, self._command_tick)
        self.create_timer(1.0, self._publish_diagnostics)
        self._publish_source()
        self._publish_diagnostics()
        if not self._hardware_output_enabled:
            self.get_logger().warning(
                "Scout hardware output is locked; commands are forced to zero"
            )

    def _declare_parameters(self) -> None:
        defaults = {
            "status_topic": "/scout_status",
            "status_timeout_s": 2.0,
            "output_topic": "/cmd_vel",
            "sent_command_topic": "/lightvln_scout/cmd_vel_sent",
            "emergency_stop_topic": "/lightvln_scout/emergency_stop",
            "control_rate_hz": 20.0,
            "input_watchdog_s": 0.35,
            "max_linear_speed": 0.30,
            "max_angular_speed": 0.60,
            "hardware_output_enabled": False,
            "require_output_subscriber": True,
        }
        for name, value in defaults.items():
            self.declare_parameter(
                name, value,
                ParameterDescriptor(
                    read_only=name not in {"max_linear_speed", "max_angular_speed"}
                ),
            )

    def _on_scout_status(self, message: ScoutStatus) -> None:
        with self._lock:
            self._telemetry.update(message, time.monotonic())

    def _on_manual(self, message: TwistStamped) -> None:
        with self._lock:
            self._manual_command = (
                float(message.twist.linear.x),
                float(message.twist.angular.z),
            )
            self._manual_received_s = time.monotonic()

    def _on_auto(self, message: TwistStamped) -> None:
        with self._lock:
            self._auto_command = (
                float(message.twist.linear.x),
                float(message.twist.angular.z),
            )
            self._auto_received_s = time.monotonic()

    def _on_emergency_stop(self, message: Bool) -> None:
        with self._lock:
            self._external_emergency = bool(message.data)
            self._emergency_stopped = bool(message.data)
            if message.data:
                self._source = "disabled"
        self._command_tick()
        self._publish_source()
        self._publish_diagnostics()
        self._publish_event(
            "emergency stop latched" if message.data else "emergency stop cleared"
        )

    def _set_manual(self, request, response):
        return self._set_source("manual" if request.data else "disabled", response)

    def _set_auto(self, request, response):
        return self._set_source("auto" if request.data else "disabled", response)

    def _set_source(self, source: str, response):
        with self._lock:
            if self._emergency_stopped and source != "disabled":
                response.success = False
                response.message = "emergency stop is latched"
                return response
            self._source = source
            self._manual_command = (0.0, 0.0)
            self._auto_command = (0.0, 0.0)
            now = time.monotonic()
            self._manual_received_s = now
            self._auto_received_s = now
        self._command_tick()
        self._publish_source()
        self._publish_diagnostics()
        response.success = True
        response.message = f"control source is {source}"
        return response

    def _stop(self, _request, response):
        return self._set_source("disabled", response)

    @staticmethod
    def _walk_mode(_request, response):
        response.success = True
        response.message = "Scout wheeled base is always in WALK mode"
        return response

    @staticmethod
    def _unsupported_mode(_request, response):
        response.success = False
        response.message = "mode is not supported by the Scout wheeled base"
        return response

    def _emergency_service(self, _request, response):
        with self._lock:
            self._emergency_stopped = True
            self._source = "disabled"
        self._command_tick()
        self._publish_source()
        self._publish_diagnostics()
        self._publish_event("web emergency stop latched")
        response.success = True
        response.message = "software emergency stop latched"
        return response

    def _reset_emergency_service(self, _request, response):
        with self._lock:
            if self._external_emergency:
                response.success = False
                response.message = "external emergency stop is still asserted"
                return response
            self._emergency_stopped = False
            self._source = "disabled"
            self._manual_command = self._auto_command = (0.0, 0.0)
            self._manual_received_s = self._auto_received_s = float("-inf")
        self._command_tick()
        self._publish_source()
        self._publish_diagnostics()
        response.success = True
        response.message = "software emergency stop cleared; control remains disabled"
        return response

    def _base_connected(self) -> bool:
        return (
            not self._require_output_subscriber
            or self._output_pub.get_subscription_count() > 0
        )

    def _on_set_parameters(self, parameters) -> SetParametersResult:
        limits = {
            "max_linear_speed": self._max_linear,
            "max_angular_speed": self._max_angular,
        }
        for parameter in parameters:
            if parameter.name not in limits:
                continue
            try:
                if isinstance(parameter.value, bool):
                    raise TypeError
                value = float(parameter.value)
            except (TypeError, ValueError):
                return SetParametersResult(
                    successful=False,
                    reason=f"{parameter.name} must be numeric",
                )
            if not math.isfinite(value) or value <= 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=f"{parameter.name} must be positive and finite",
                )
            hard_limit = (
                self._hard_max_linear
                if parameter.name == "max_linear_speed"
                else self._hard_max_angular
            )
            if value > hard_limit:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f"{parameter.name} exceeds launch safety limit "
                        f"{hard_limit}"
                    ),
                )
            limits[parameter.name] = value
        with self._lock:
            self._max_linear = limits["max_linear_speed"]
            self._max_angular = limits["max_angular_speed"]
        return SetParametersResult(successful=True)

    def _command_tick(self) -> None:
        now = time.monotonic()
        with self._lock:
            command = select_command(
                source=self._source,
                manual_command=self._manual_command,
                manual_age_s=now - self._manual_received_s,
                auto_command=self._auto_command,
                auto_age_s=now - self._auto_received_s,
                watchdog_s=self._watchdog_s,
                max_linear=self._max_linear,
                max_angular=self._max_angular,
                hardware_output_enabled=(
                    self._hardware_output_enabled and self._base_connected()
                ),
                emergency_stopped=self._emergency_stopped,
            )
        output = Twist()
        output.linear.x, output.angular.z = command
        self._output_pub.publish(output)
        sent = TwistStamped()
        sent.header.stamp = self.get_clock().now().to_msg()
        sent.header.frame_id = "base_link"
        sent.twist = output
        self._sent_pub.publish(sent)

    def _publish_source(self) -> None:
        with self._lock:
            source = self._source
        self._source_pub.publish(String(data=source))

    def _publish_event(self, text: str) -> None:
        self._event_pub.publish(String(data=text))

    def _publish_diagnostics(self) -> None:
        connected = self._base_connected()
        with self._lock:
            source = self._source
            emergency = self._emergency_stopped
            telemetry = self._telemetry.snapshot(time.monotonic())
        status = build_diagnostic_status(
            connected=connected,
            source=source,
            emergency=emergency,
            hardware_output_enabled=self._hardware_output_enabled,
            telemetry=telemetry,
        )
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status.append(status)
        self._diagnostics_pub.publish(array)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._lock:
            self._source = "disabled"
        for _ in range(3):
            with contextlib.suppress(Exception):
                self._output_pub.publish(Twist())

    def destroy_node(self) -> bool:
        self.close()
        return super().destroy_node()


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ScoutAdapterNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        with contextlib.suppress(Exception, KeyboardInterrupt):
            node.close()
        with contextlib.suppress(Exception, KeyboardInterrupt):
            node.destroy_node()
        with contextlib.suppress(Exception, KeyboardInterrupt):
            if rclpy.ok():
                rclpy.shutdown()


if __name__ == "__main__":
    main()
