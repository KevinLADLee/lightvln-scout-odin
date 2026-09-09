"""Read deployment defaults from the stack's ROS 2 parameter file."""

from __future__ import annotations

import math
from pathlib import Path

import yaml
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration

_SOURCES = {
    "server_url": ("vln_client", "server_url", str),
    "web_port": ("vln_web", "port", int),
    "motion_enabled": ("scout_adapter", "hardware_output_enabled", bool),
    "require_output_subscriber": ("scout_adapter", "require_output_subscriber", bool),
    "scout_port": ("robot_launch", "scout_port", str),
    **{
        f"imu_to_base_{axis}": ("robot_launch", f"imu_to_base_{axis}", float)
        for axis in ("x", "y", "z", "roll", "pitch", "yaw")
    },
}


def _read_parameters(path):
    with Path(path).open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected a ROS 2 parameter mapping")
    result = {}
    for node, section in document.items():
        if not isinstance(section, dict) or not isinstance(section.get("ros__parameters"), dict):
            raise ValueError(f"{path}: {node} must contain a ros__parameters mapping")
        result[node] = section["ros__parameters"]
    return result


def _load_defaults(context, *, defaults_file, default_file, profile):
    parameters = _read_parameters(defaults_file)
    selected_file = LaunchConfiguration("params_file").perform(context)
    for path in dict.fromkeys([default_file, selected_file]):
        for node, overrides in _read_parameters(path).items():
            parameters.setdefault(node, {}).update(overrides)
    sources = {**_SOURCES, "launch_scout_base": (profile, "launch_scout_base", bool)}
    for argument, (node, parameter, expected_type) in sources.items():
        value = parameters[node][parameter]
        if expected_type is float:
            valid = type(value) in (int, float) and math.isfinite(value)
        else:
            valid = type(value) is expected_type
        if not valid:
            raise ValueError(
                f"{selected_file}: {node}.{parameter} must be a finite number"
                if expected_type is float else
                f"{selected_file}: {node}.{parameter} must be {expected_type.__name__}"
            )
        if argument == "web_port" and not 1 <= value <= 65535:
            raise ValueError(f"{selected_file}: vln_web.port must be between 1 and 65535")
        # Internal defaults keep explicit command-line overrides working.
        context.launch_configurations[f"preset_{argument}"] = (
            str(value).lower() if expected_type is bool else str(value)
        )
    return []


def preset_launch_arguments(default_file, *, defaults_file, profile):
    """Declare a parameter-file preset and optional per-value overrides."""
    return [
        DeclareLaunchArgument(
            "params_file", default_value=default_file,
            description="ROS 2 parameter YAML; overlays the installed standard_stack.yaml",
        ),
        OpaqueFunction(
            function=_load_defaults,
            kwargs={
                "defaults_file": defaults_file, "default_file": default_file, "profile": profile,
            },
        ),
        *[
            DeclareLaunchArgument(
                name, default_value=LaunchConfiguration(f"preset_{name}"),
                description="Optional override of the YAML preset",
            )
            for name in [*_SOURCES, "launch_scout_base"]
        ],
    ]
