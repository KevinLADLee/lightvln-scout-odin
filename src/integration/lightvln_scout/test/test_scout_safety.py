import math

import pytest

from lightvln_scout.safety import select_command


def command(**overrides):
    values = {
        "source": "auto",
        "manual_command": (0.1, 0.2),
        "manual_age_s": 0.1,
        "auto_command": (0.2, -0.3),
        "auto_age_s": 0.1,
        "watchdog_s": 0.35,
        "max_linear": 0.3,
        "max_angular": 0.6,
        "hardware_output_enabled": True,
        "emergency_stopped": False,
    }
    values.update(overrides)
    return select_command(**values)


def test_selects_only_the_active_fresh_source():
    assert command() == (0.2, -0.3)
    assert command(source="manual") == (0.1, 0.2)
    assert command(source="disabled") == (0.0, 0.0)
    assert command(auto_age_s=0.36) == (0.0, 0.0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"hardware_output_enabled": False},
        {"emergency_stopped": True},
        {"auto_command": (0.31, 0.0)},
        {"auto_command": (0.0, 0.61)},
        {"auto_command": (math.nan, 0.0)},
    ],
)
def test_safety_conditions_force_zero(overrides):
    assert command(**overrides) == (0.0, 0.0)


@pytest.mark.parametrize("field", ["auto_age_s", "watchdog_s", "max_linear", "max_angular"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_age_and_limits_fail_closed(field, value):
    assert command(**{field: value}) == (0.0, 0.0)
