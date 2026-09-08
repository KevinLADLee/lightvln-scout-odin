"""Pure command arbitration for the Scout adapter."""

from __future__ import annotations

import math


def select_command(
    *,
    source: str,
    manual_command: tuple[float, float],
    manual_age_s: float,
    auto_command: tuple[float, float],
    auto_age_s: float,
    watchdog_s: float,
    max_linear: float,
    max_angular: float,
    hardware_output_enabled: bool,
    emergency_stopped: bool,
) -> tuple[float, float]:
    """Return a bounded active command or an explicit zero command."""
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (watchdog_s, max_linear, max_angular)
    ):
        return (0.0, 0.0)
    if not hardware_output_enabled or emergency_stopped:
        return (0.0, 0.0)
    command = None
    age_s = math.inf
    if source == "manual":
        command, age_s = manual_command, manual_age_s
    elif source == "auto":
        command, age_s = auto_command, auto_age_s
    if (
        command is None or not math.isfinite(age_s)
        or age_s < 0.0 or age_s > watchdog_s
    ):
        return (0.0, 0.0)
    linear, angular = command
    if (
        not math.isfinite(linear)
        or not math.isfinite(angular)
        or abs(linear) > max_linear
        or abs(angular) > max_angular
    ):
        return (0.0, 0.0)
    return (linear, angular)
