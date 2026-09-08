# SCOUT ROS 2

[![Build](https://github.com/Hive-Matrix-AI/scout_ros2/actions/workflows/ros-ci.yml/badge.svg?branch=humble)](https://github.com/Hive-Matrix-AI/scout_ros2/actions/workflows/ros-ci.yml)
[![ROS 2](https://img.shields.io/badge/ROS%202-Humble%20%7C%20Jazzy-22314E?logo=ros&logoColor=white)](#supported-configurations)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-E95420?logo=ubuntu&logoColor=white)](#supported-configurations)
[![SocketCAN](https://img.shields.io/badge/transport-SocketCAN-3C8D6E)](#connect-the-robot)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**Bring SCOUT MINI and SCOUT MINI OMNI into your ROS 2 application.**

Control your base through standard velocity commands, read robot feedback, and
inspect the connection from a terminal dashboard. A shared SocketCAN driver
supports both skid-steer and omnidirectional configurations.

[Quick start](#quick-start) · [Supported configurations](#supported-configurations) ·
[Terminal dashboard](#terminal-dashboard) · [Driver reference](scout_base/README.md) ·
[Changelog](CHANGELOG.md)

## Highlights

- **Standard ROS interfaces.** `cmd_vel` input, wheel odometry, TF, and typed
  status messages for battery, motors, lights, and remote control.
- **Two drive configurations.** Select SCOUT MINI or SCOUT MINI OMNI with one
  launch argument, including lateral velocity for OMNI.
- **Built-in commissioning tools.** A terminal dashboard with guarded motion
  controls, plus automated CAN feedback and low-speed diagnostics.
- **Tested across distributions.** CI builds and tests Humble and Jazzy,
  including installed launch files and the Python console entry point.

## Supported configurations

| Robot | Launch selection |
| --- | --- |
| SCOUT MINI | Default, skid-steer |
| SCOUT MINI OMNI | `omni:=true` |

| ROS 2 | Ubuntu |
| --- | --- |
| Humble | 22.04 LTS (Jammy) |
| Jazzy | 24.04 LTS (Noble) |

Both distributions use the same source on the `humble` branch. The hardware
connection uses **SocketCAN at 500 kbit/s**.

## Quick start

### Build the workspace

Requires ROS 2 **ROS Base** or **Desktop**. Install the build tools and Xacro
directly with APT:

The example uses Jazzy. On Ubuntu 22.04, replace the first line with
`source /opt/ros/humble/setup.bash`. Use separate workspaces for each distribution.

```bash
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install -y build-essential cmake python3-colcon-common-extensions \
  "ros-${ROS_DISTRO}-xacro"
mkdir -p ~/scout_ws/src
cd ~/scout_ws/src
git clone --branch humble --recurse-submodules https://github.com/Hive-Matrix-AI/scout_ros2.git
cd ~/scout_ws
colcon build --symlink-install
source install/setup.bash
```

The SDK is included as a Git submodule. For an existing checkout, run
`git submodule update --init --recursive` from the repository root before
building. See [SDK dependency](third_party/README.md) for other installation layouts.

### Connect the robot

Use a SocketCAN adapter and replace `can0` with its interface name if needed:

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 restart-ms 100
sudo ip link set can0 up
ip -details -statistics link show can0
```

For the first motion test, raise the wheels off the ground, clear the robot's
motion envelope, and keep the physical emergency stop within reach.

### Start the driver

Power on the base and release its emergency stop when ready to operate:

```bash
ros2 launch scout_base scout_mini.launch.py
```

For SCOUT MINI OMNI:

```bash
ros2 launch scout_base scout_mini.launch.py omni:=true
```

The driver enables CAN commanded mode on connection. A command watchdog sends
zero velocity after **0.5 s** without a new `cmd_vel`; shutdown also sends
zero-speed frames. These controls do not replace the physical emergency stop.

## Terminal dashboard

With the driver running, open another terminal:

```bash
source ~/scout_ws/install/setup.bash
ros2 run scout_base scout_test_tui
```

View CAN state, topic freshness, battery voltage, motor telemetry, odometry,
lights, and remote-control inputs in one place. Motion output starts **locked**.
Use uppercase `E` to arm it; `Space` or `Esc` sends zero velocity and locks it again.

For lower test speeds:

```bash
ros2 run scout_base scout_test_tui --linear-speed 0.08 --angular-speed 0.20
```

See [dashboard controls](scout_base/README.md#terminal-dashboard) for key bindings,
OMNI operation, and remapping, or [CAN diagnostics](scout_base/README.md#can-diagnostics)
for automated checks.

## Packages and interfaces

| Package | Purpose |
| --- | --- |
| [`scout_base`](scout_base/README.md) | Driver, command watchdog, terminal dashboard, and CAN diagnostics |
| [`scout_msgs`](scout_msgs/msg) | Robot status, actuator, remote-control, and light-control messages |
| [`scout_description`](scout_base/README.md#robot-description) | Bundled SCOUT V2 URDF and meshes |

The driver accepts `cmd_vel` (`geometry_msgs/msg/Twist`) and `light_control`.
It publishes `scout_status`, `rc_status`, `odom`, and the `odom` → `base_link` TF.
OMNI also uses `cmd_vel.linear.y` for lateral motion.

The bundled description is a SCOUT V2 model with fixed wheel joints. Use
vehicle-specific geometry for SCOUT MINI or OMNI collision checking.

CAN communication is provided by
[`agilex_ugv_sdk`](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk), a
general-purpose C++ SDK for new AgileX models. SCOUT-specific ROS integrations
are maintained in this repository.

## Documentation

- [Launch parameters](scout_base/README.md#launch-options)
- [ROS topics and message contracts](scout_base/README.md#ros-interface)
- [Troubleshooting](scout_base/README.md#troubleshooting)
- [SCOUT MINI CAN protocol](third_party/agilex_ugv_sdk/docs/reference/models/scout/scout_mini_can.md)
- [Contributing and running tests](CONTRIBUTING.md)

Bug reports and pull requests are welcome through
[GitHub Issues](https://github.com/Hive-Matrix-AI/scout_ros2/issues) and
[Pull Requests](https://github.com/Hive-Matrix-AI/scout_ros2/pulls).

## License

The driver and SDK are licensed under **Apache-2.0**. The wheel Xacro files retain
their **BSD-3-Clause** notices. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
