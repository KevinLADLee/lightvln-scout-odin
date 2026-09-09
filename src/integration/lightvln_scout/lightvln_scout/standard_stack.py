"""Shared launch construction for the standard LightNav robot stack."""

from __future__ import annotations

from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def standard_stack_nodes(
    *,
    stack_params,
    preset_params,
    server_url,
    web_port,
    hardware_output_enabled,
    require_output_subscriber,
    imu_to_base_xyyaw: list[float],
    params_file=None,
) -> list[Node]:
    """Create the LightNav stack for Odin and Scout."""
    overrides = [preset_params]
    if params_file is not None:
        overrides.append(params_file)
    return [
        Node(
            package="lightvln_scout",
            executable="scout_vln_client",
            name="vln_client",
            output="screen",
            parameters=[
                stack_params, *overrides,
                {"server_url": ParameterValue(server_url, value_type=str)},
            ],
        ),
        Node(
            package="lightvln_scout",
            executable="scout_vln_web",
            name="vln_web",
            output="screen",
            parameters=[
                stack_params,
                *overrides,
                {
                    "port": ParameterValue(web_port, value_type=int),
                    "controller_node": "/vln_mpc",
                    "controller_config_enabled": True,
                },
            ],
        ),
        Node(
            package="vln_mpc",
            executable="vln_mpc",
            name="vln_mpc",
            output="screen",
            parameters=[
                stack_params,
                *overrides,
                {"odom_child_to_base_xyyaw": imu_to_base_xyyaw},
            ],
        ),
        Node(
            package="lightvln_scout",
            executable="scout_adapter",
            name="scout_adapter",
            output="screen",
            parameters=[
                stack_params,
                *overrides,
                {
                    "hardware_output_enabled": ParameterValue(
                        hardware_output_enabled, value_type=bool
                    ),
                    "require_output_subscriber": ParameterValue(
                        require_output_subscriber, value_type=bool
                    ),
                },
            ],
        ),
    ]
