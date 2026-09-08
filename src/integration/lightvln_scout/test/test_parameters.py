import rclpy
from rclpy.parameter import Parameter

from lightvln_scout.node import ScoutAdapterNode


def test_web_speed_limits_update_adapter_but_cannot_raise_launch_limits(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path))
    rclpy.init(args=[])
    node = ScoutAdapterNode()
    try:
        result = node.set_parameters_atomically(
            [Parameter("max_linear_speed", value=0.2)]
        )
        assert result.successful
        assert node._max_linear == 0.2

        result = node.set_parameters_atomically(
            [Parameter("max_linear_speed", value=0.31)]
        )
        assert not result.successful
        assert "launch safety limit" in result.reason
        assert node._max_linear == 0.2
    finally:
        node.destroy_node()
        rclpy.shutdown()


def test_emergency_reset_cannot_override_external_stop_or_resume_commands(
    monkeypatch, tmp_path
):
    from geometry_msgs.msg import TwistStamped
    from std_msgs.msg import Bool
    from std_srvs.srv import SetBool, Trigger

    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path))
    rclpy.init(args=[])
    node = ScoutAdapterNode()
    try:
        assert not node.set_parameters_atomically([
            Parameter("hardware_output_enabled", value=True)
        ]).successful
        node._set_source("manual", SetBool.Response())
        command = TwistStamped()
        command.twist.linear.x = 0.1
        node._on_manual(command)
        result = node._emergency_service(None, Trigger.Response())
        assert result.success and node._source == "disabled"
        assert not node._set_source("auto", SetBool.Response()).success
        node._on_emergency_stop(Bool(data=True))
        assert not node._reset_emergency_service(None, Trigger.Response()).success
        node._on_emergency_stop(Bool(data=False))
        node._emergency_service(None, Trigger.Response())
        assert node._reset_emergency_service(None, Trigger.Response()).success
        assert node._source == "disabled"
        assert node._manual_command == (0.0, 0.0)
        assert not node._emergency_stopped
    finally:
        node.destroy_node()
        rclpy.shutdown()
