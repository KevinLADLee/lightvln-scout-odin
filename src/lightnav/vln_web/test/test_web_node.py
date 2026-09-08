from vln_web.web_node import response_latency_ms


def test_reported_round_trip_latency_ignores_sensor_clock_domain():
    assert response_latency_ms(
        42.5,
        capture_stamp_ns=5_000_000_000,
        now_ns=1_788_271_470_000_000_000,
    ) == 42.5


def test_legacy_response_latency_uses_matching_clock_when_available():
    assert response_latency_ms(
        None,
        capture_stamp_ns=9_950_000_000,
        now_ns=10_000_000_000,
    ) == 50.0


def test_scout_diagnostics_preserve_safety_and_voltage_fields():
    from types import SimpleNamespace

    from vln_web.web_node import VlnWebNode

    result = VlnWebNode._parse_robot_diagnostics(
        SimpleNamespace(level=bytes([1]), message="output locked"),
        {"adapter": "scout_ros2", "connected": "true",
         "hardware_output_enabled": "false", "emergency_stopped": "true",
         "battery_voltage": "25.4", "telemetry_fresh": "true",
         "error_code": "4", "supported_actions": "emergency_stop,reset_emergency_stop"},
    )
    assert result["battery"] is None
    assert result["battery_voltage"] == 25.4
    assert result["emergency_stopped"] is True
    assert result["hardware_output_enabled"] is False
    assert result["supported_actions"] == ["emergency_stop", "reset_emergency_stop"]
