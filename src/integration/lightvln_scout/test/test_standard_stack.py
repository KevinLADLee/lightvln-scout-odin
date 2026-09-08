from pathlib import Path

import yaml

from lightvln_scout.standard_stack import standard_stack_nodes


def test_standard_stack_keeps_original_lightnav_control_chain(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path))
    nodes = standard_stack_nodes(
        stack_params="stack.yaml",
        mpc_params="mpc.yaml",
        server_url="ws://server:8050",
        web_port=8088,
        hardware_output_enabled=False,
        require_output_subscriber=False,
        imu_to_base_xyyaw=[-0.18, 0.0, 0.0],
    )

    assert [
        (node.node_package, node.node_executable) for node in nodes
    ] == [
        ("lightvln_scout", "scout_vln_client"),
        ("lightvln_scout", "scout_vln_web"),
        ("vln_mpc", "vln_mpc"),
        ("lightvln_scout", "scout_adapter"),
    ]


def test_upstream_mpc_matches_default_odin_odometry_frames():
    config_path = Path(__file__).parents[1] / "config" / "upstream_mpc.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    parameters = config["vln_mpc"]["ros__parameters"]

    assert parameters["odom_topic"] == "/odin1/odometry_highfreq"
    assert parameters["odom_frame"] == "odom"
    assert parameters["odom_child_frame"] == "imu"
    assert parameters["base_frame"] == "base_link"
