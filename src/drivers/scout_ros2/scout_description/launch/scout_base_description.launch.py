# SPDX-License-Identifier: Apache-2.0

"""Publish the bundled SCOUT V2 robot description."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Create the robot state publisher and its clock argument."""
    model = PathJoinSubstitution([
        FindPackageShare('scout_description'), 'urdf', 'scout_v2.xacro',
    ])
    description = ParameterValue(
        Command([FindExecutable(name='xacro'), ' ', model]), value_type=str,
    )
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time', default_value='false',
            description='Use the simulation clock',
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'robot_description': description,
            }],
        ),
    ])
