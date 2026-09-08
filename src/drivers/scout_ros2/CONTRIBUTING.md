# Contributing

## Report a problem

Open an [issue](https://github.com/Hive-Matrix-AI/scout_ros2/issues) with the
robot model, ROS distribution, operating system, launch command, expected
behavior, and steps to reproduce. Include relevant logs after removing
credentials, personal data, and private network details.

For motion-related problems, describe the emergency-stop state and whether the
robot was raised off the ground. Never repeat an unsafe motion to collect logs.

## Submit a change

Target the `humble` branch, which supports both Humble and Jazzy. Keep changes
focused, add regression tests when behavior changes, and update the public
documentation for interface changes.
Preserve existing license and attribution notices.

SCOUT ROS nodes, launch files, and diagnostics belong in this repository.
Shared C++ APIs and CAN protocol changes belong in
[`agilex_ugv_sdk`](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk).
An SDK update must be available in that repository before changing the submodule
revision here.

CI builds and tests Humble on Ubuntu 22.04 and Jazzy on Ubuntu 24.04. Install the
dependencies in the [quick start](README.md#quick-start) and use separate
workspaces for each distribution. From a workspace containing the repository and
its initialized submodule:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --cmake-args -DBUILD_TESTING=ON
source install/setup.bash
colcon test
colcon test-result --verbose
ros2 launch scout_base scout_mini.launch.py --show-args
ros2 launch scout_description scout_base_description.launch.py --show-args
ros2 run scout_base scout_test_tui --help
```

For Humble, source `/opt/ros/humble/setup.bash` instead. These tests and entry-point
checks do not require robot hardware. If you also test on a robot, state
the model and test conditions in the pull request. Keep the emergency stop
within reach and use the safety precautions in the [README](README.md).
