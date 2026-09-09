"""Full Odin, LightNav, and Scout stack."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from lightvln_scout.launch_config import preset_launch_arguments
from lightvln_scout.standard_stack import standard_stack_nodes


def _scout_base(context):
    enabled = LaunchConfiguration("launch_scout_base").perform(context).lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return []
    scout_share = get_package_share_directory("scout_base")
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(scout_share, "launch", "scout_mini.launch.py")
            ),
            launch_arguments={
                "port_name": LaunchConfiguration("scout_port"),
                "odom_frame": "scout_wheel_odom",
                "base_frame": "scout_wheel_base",
                "odom_topic_name": "/scout/wheel_odom",
            }.items(),
        )
    ]


def _stack(
    context,
    *,
    stack_params,
    preset_params,
):
    imu_to_base = [
        float(LaunchConfiguration("imu_to_base_x").perform(context)),
        float(LaunchConfiguration("imu_to_base_y").perform(context)),
        float(LaunchConfiguration("imu_to_base_yaw").perform(context)),
    ]
    return standard_stack_nodes(
        stack_params=stack_params,
        preset_params=preset_params,
        params_file=LaunchConfiguration("params_file"),
        server_url=LaunchConfiguration("server_url"),
        web_port=LaunchConfiguration("web_port"),
        hardware_output_enabled=LaunchConfiguration("motion_enabled"),
        require_output_subscriber=LaunchConfiguration("require_output_subscriber"),
        imu_to_base_xyyaw=imu_to_base,
    )


def generate_launch_description() -> LaunchDescription:
    share = get_package_share_directory("lightvln_scout")
    odin_share = get_package_share_directory("odin_ros_driver")
    stack_params = os.path.join(share, "config", "defaults.yaml")
    preset_params = os.path.join(share, "config", "standard_stack.yaml")
    odin_launch = os.path.join(odin_share, "launch", "odin1_ros2.launch.py")
    arguments = preset_launch_arguments(
        preset_params, defaults_file=stack_params, profile="scout_odin",
    )
    static_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="imu_to_base_link",
        arguments=[
            LaunchConfiguration("imu_to_base_x"),
            LaunchConfiguration("imu_to_base_y"),
            LaunchConfiguration("imu_to_base_z"),
            LaunchConfiguration("imu_to_base_yaw"),
            LaunchConfiguration("imu_to_base_pitch"),
            LaunchConfiguration("imu_to_base_roll"),
            "imu",
            "base_link",
        ],
    )
    stack = OpaqueFunction(
        function=_stack,
        kwargs={
            "stack_params": stack_params,
            "preset_params": preset_params,
        },
    )
    scout_base = OpaqueFunction(function=_scout_base)
    return LaunchDescription(
        arguments
        + [
            IncludeLaunchDescription(PythonLaunchDescriptionSource(odin_launch)),
            scout_base,
            static_tf,
            stack,
        ]
    )
