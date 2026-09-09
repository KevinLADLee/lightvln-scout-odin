"""Resolve real launch descriptions without starting drivers or moving a robot."""

import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml
from launch import LaunchContext
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.utilities import normalize_to_list_of_substitutions, perform_substitutions
from launch_ros.actions import Node
from launch_ros.utilities import evaluate_parameters

PACKAGE = Path(__file__).parents[1]


def resolve_launch(profile, tmp_path, monkeypatch, preset=None, **cli):
    monkeypatch.setenv("ROS_LOG_DIR", str(tmp_path / "logs"))
    spec = importlib.util.spec_from_file_location(
        profile, PACKAGE / "launch" / f"{profile}.launch.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    get_share = module.get_package_share_directory
    monkeypatch.setattr(
        module,
        "get_package_share_directory",
        lambda name: str(PACKAGE) if name == "lightvln_scout" else get_share(name),
    )
    context = LaunchContext()
    if preset is not None:
        config_file = tmp_path / "robot.yaml"
        config_file.write_text(yaml.safe_dump(preset))
        context.launch_configurations["params_file"] = str(config_file)
    context.launch_configurations.update(cli)
    actions = []
    for action in module.generate_launch_description().entities:
        if isinstance(action, (DeclareLaunchArgument, OpaqueFunction)):
            actions.extend(action.execute(context) or [])
        else:
            actions.append(action)
    return context, actions


def node_parameters(node, context, name):
    # Evaluate the actual launch_ros parameter list, including YAML precedence.
    result = {}
    for source in evaluate_parameters(context, node._Node__parameters):
        if isinstance(source, dict):
            result.update(source)
        else:
            document = yaml.safe_load(source.read_text())
            result.update(document.get(name, {}).get("ros__parameters", {}))
    return result


@pytest.mark.parametrize("profile,base_enabled", [("scout_odin", True), ("controller_only", False)])
def test_default_launch_uses_yaml_driver_selection_and_locks_motion(
    profile, base_enabled, tmp_path, monkeypatch
):
    context, actions = resolve_launch(profile, tmp_path, monkeypatch)
    assert context.launch_configurations["launch_scout_base"] == str(base_enabled).lower()
    adapter = next(
        a for a in actions if isinstance(a, Node) and a.node_executable == "scout_adapter"
    )
    parameters = node_parameters(adapter, context, "scout_adapter")
    assert parameters["hardware_output_enabled"] is False
    assert parameters["require_output_subscriber"] is True


@pytest.mark.parametrize("profile", ["scout_odin", "controller_only"])
def test_yaml_reaches_nodes_driver_and_matching_tf_mpc_offsets(profile, tmp_path, monkeypatch):
    context, actions = resolve_launch(
        profile,
        tmp_path,
        monkeypatch,
        {
            "robot_launch": {
                "ros__parameters": {
                    "scout_port": "can7",
                    "imu_to_base_x": 0.12,
                    "imu_to_base_y": -0.03,
                    "imu_to_base_z": 0.42,
                    "imu_to_base_roll": 0.01,
                    "imu_to_base_pitch": -0.02,
                    "imu_to_base_yaw": 0.3,
                }
            },
            profile: {"ros__parameters": {"launch_scout_base": True}},
            "vln_client": {"ros__parameters": {"server_url": "ws://gpu.example:8051"}},
            "vln_web": {"ros__parameters": {"port": 8099}},
            "scout_adapter": {
                "ros__parameters": {
                    "hardware_output_enabled": True,
                    "max_linear_speed": 0.17,
                }
            },
            "vln_mpc": {"ros__parameters": {"track_v_max": 0.17}},
        },
    )
    nodes = {a.node_executable: a for a in actions if isinstance(a, Node)}
    client = node_parameters(nodes["scout_vln_client"], context, "vln_client")
    assert client["server_url"] == "ws://gpu.example:8051"
    assert client["image_width"] == 448  # Unspecified values retain the installed preset.
    web = node_parameters(nodes["scout_vln_web"], context, "vln_web")
    assert web["port"] == 8099
    adapter = node_parameters(nodes["scout_adapter"], context, "scout_adapter")
    assert adapter["hardware_output_enabled"] is True
    assert adapter["max_linear_speed"] == 0.17
    mpc = node_parameters(nodes["vln_mpc"], context, "vln_mpc")
    assert mpc["track_v_max"] == 0.17
    assert tuple(mpc["odom_child_to_base_xyyaw"]) == (0.12, -0.03, 0.3)
    tf_args = [
        perform_substitutions(context, arg) for arg in nodes["static_transform_publisher"].cmd[1:9]
    ]
    assert tf_args == ["0.12", "-0.03", "0.42", "0.3", "-0.02", "0.01", "imu", "base_link"]
    base = next(
        a for a in actions if isinstance(a, IncludeLaunchDescription) and a.launch_arguments
    )
    port = dict(base.launch_arguments)["port_name"]
    assert perform_substitutions(context, normalize_to_list_of_substitutions(port)) == "can7"


def test_explicit_overrides_take_priority_over_yaml(tmp_path, monkeypatch):
    context, actions = resolve_launch(
        "controller_only",
        tmp_path,
        monkeypatch,
        {
            "vln_web": {"ros__parameters": {"port": 8099}},
            "scout_adapter": {"ros__parameters": {"hardware_output_enabled": True}},
        },
        web_port="8100",
        motion_enabled="false",
        imu_to_base_x="0.2",
    )
    nodes = {a.node_executable: a for a in actions if isinstance(a, Node)}
    assert node_parameters(nodes["scout_vln_web"], context, "vln_web")["port"] == 8100
    assert (
        node_parameters(nodes["scout_adapter"], context, "scout_adapter")["hardware_output_enabled"]
        is False
    )
    assert (
        node_parameters(nodes["vln_mpc"], context, "vln_mpc")["odom_child_to_base_xyyaw"][0] == 0.2
    )


@pytest.mark.parametrize(
    "node,key,value",
    [
        ("scout_adapter", "hardware_output_enabled", "false"),
        ("vln_web", "port", 70000),
        ("robot_launch", "imu_to_base_x", float("nan")),
        ("robot_launch", "imu_to_base_yaw", True),
    ],
)
def test_invalid_preset_fails_before_driver_actions(node, key, value, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match=f"{node}.{key}"):
        resolve_launch(
            "scout_odin",
            tmp_path,
            monkeypatch,
            {
                node: {"ros__parameters": {key: value}},
            },
        )


def test_missing_preset_fails_before_driver_actions(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError):
        resolve_launch(
            "scout_odin", tmp_path, monkeypatch, params_file=str(tmp_path / "missing.yaml")
        )


def test_partial_machine_file_retains_saved_robot_settings(tmp_path, monkeypatch):
    package = tmp_path / "package"
    shutil.copytree(PACKAGE / "launch", package / "launch")
    shutil.copytree(PACKAGE / "config", package / "config")
    preset_path = package / "config" / "standard_stack.yaml"
    preset = yaml.safe_load(preset_path.read_text())
    preset["vln_client"]["ros__parameters"]["server_url"] = "ws://saved-robot.example:8050"
    preset["robot_launch"]["ros__parameters"]["imu_to_base_x"] = 0.23
    preset["scout_adapter"]["ros__parameters"]["hardware_output_enabled"] = True
    preset_path.write_text(yaml.safe_dump(preset))
    monkeypatch.setitem(globals(), "PACKAGE", package)
    context, actions = resolve_launch("controller_only", tmp_path, monkeypatch, {
        "vln_web": {"ros__parameters": {"port": 8099}},
    })
    nodes = {a.node_executable: a for a in actions if isinstance(a, Node)}
    client = node_parameters(nodes["scout_vln_client"], context, "vln_client")
    adapter = node_parameters(nodes["scout_adapter"], context, "scout_adapter")
    mpc = node_parameters(nodes["vln_mpc"], context, "vln_mpc")
    assert client["server_url"] == "ws://saved-robot.example:8050"
    assert adapter["hardware_output_enabled"] is True
    assert mpc["odom_child_to_base_xyyaw"][0] == 0.23
    assert node_parameters(nodes["scout_vln_web"], context, "vln_web")["port"] == 8099
