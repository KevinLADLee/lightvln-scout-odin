from diagnostic_msgs.msg import DiagnosticStatus

from lightvln_scout.node import build_diagnostic_status


def test_diagnostics_match_vln_web_robot_adapter_contract():
    status = build_diagnostic_status(
        connected=True,
        source="disabled",
        emergency=False,
        hardware_output_enabled=False,
    )
    values = {item.key: item.value for item in status.values}

    assert status.name == "robot_adapter"
    assert status.hardware_id == "scout"
    assert status.level == DiagnosticStatus.WARN
    assert values["adapter"] == "scout_ros2"
    assert values["connected"] == "true"
    assert values["mode"] == "WALK"
    assert values["imu"] == "UNKNOWN"
    assert values["motor"] == "UNKNOWN"
    assert values["control_source"] == "disabled"
    assert values["supported_actions"] == "emergency_stop,reset_emergency_stop"
    assert values["hardware_output_enabled"] == "false"



def test_base_fault_is_visible_even_with_output_locked():
    status = build_diagnostic_status(
        connected=True, source="disabled", emergency=False,
        hardware_output_enabled=False,
        telemetry={"telemetry_fresh": "true", "error_code": "4"},
    )
    assert status.level == DiagnosticStatus.ERROR
    assert "base fault" in status.message
