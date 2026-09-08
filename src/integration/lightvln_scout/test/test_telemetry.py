from types import SimpleNamespace

import pytest

from lightvln_scout.telemetry import ScoutTelemetry


def test_telemetry_expires_and_recovers_without_inventing_percentage():
    telemetry = ScoutTelemetry(timeout_s=2.0)
    assert telemetry.snapshot(1.0)["telemetry_fresh"] == "false"
    telemetry.update(SimpleNamespace(
        battery_voltage=25.4, vehicle_state=0, control_mode=1, error_code=4,
    ), 10.0)
    fresh = telemetry.snapshot(11.0)
    assert fresh["battery_voltage"] == "25.4"
    assert fresh["error_code"] == "4"
    assert "battery" not in fresh and "motor" not in fresh
    assert "battery_voltage" not in telemetry.snapshot(12.1)
    assert telemetry.snapshot(9.0)["telemetry_fresh"] == "false"


@pytest.mark.parametrize("voltage", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_voltage_stays_unknown(voltage):
    telemetry = ScoutTelemetry()
    telemetry.update(SimpleNamespace(
        battery_voltage=voltage, vehicle_state=0, control_mode=0, error_code=0,
    ), 1.0)
    assert telemetry.snapshot(1.0)["battery_voltage"] == ""
