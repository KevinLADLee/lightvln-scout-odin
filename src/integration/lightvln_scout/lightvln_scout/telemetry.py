"""Translate Scout telemetry without guessing battery percentage or motor health.

ScoutStatus has no per-CAN-frame freshness/validity flags. Reception freshness
therefore describes the ROS publisher, not proof that the CAN bus is healthy.
"""

from __future__ import annotations

import math


class ScoutTelemetry:
    def __init__(self, timeout_s: float = 2.0) -> None:
        if not math.isfinite(timeout_s) or timeout_s <= 0.0:
            raise ValueError("status_timeout_s must be positive and finite")
        self.timeout_s = timeout_s
        self._received_s = -math.inf
        self._values: dict[str, str] = {}

    def update(self, message, now_s: float) -> None:
        voltage = float(message.battery_voltage)
        self._values = {
            "battery_voltage": (
                str(voltage) if math.isfinite(voltage) and voltage > 0.0 else ""
            ),
            "vehicle_state": str(int(message.vehicle_state)),
            "control_mode": str(int(message.control_mode)),
            "error_code": str(int(message.error_code)),
        }
        self._received_s = now_s

    def snapshot(self, now_s: float) -> dict[str, str]:
        age = now_s - self._received_s
        fresh = math.isfinite(age) and 0.0 <= age <= self.timeout_s
        result = {
            "telemetry_fresh": str(fresh).lower(),
            "telemetry_age_s": str(age) if math.isfinite(age) else "",
        }
        if fresh:
            result.update(self._values)
        return result
