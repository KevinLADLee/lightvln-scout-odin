# scout_base

`scout_base` is the ROS 2 hardware driver for SCOUT MINI and SCOUT MINI
OMNI. It connects to the base through SocketCAN, publishes robot state and
wheel-integrated odometry, broadcasts `odom` to `base_link`, and accepts
`geometry_msgs/msg/Twist` velocity commands.

Supported environments are Humble on Ubuntu 22.04 and Jazzy on Ubuntu 24.04.

For installation and CAN configuration, see the
[repository quick start](../README.md#quick-start).

## Start the driver

```bash
ros2 launch scout_base scout_mini.launch.py
```

Use `omni:=true` for SCOUT MINI OMNI. The driver enables CAN commanded mode at
startup and applies a zero-speed watchdog when `cmd_vel` becomes stale.
Shutdown sends several zero-speed frames without selecting standby mode.

## Launch options

```bash
ros2 launch scout_base scout_mini.launch.py \
  port_name:=can0 \
  omni:=false \
  odom_frame:=odom \
  base_frame:=base_link \
  odom_topic_name:=odom \
  control_rate:=50 \
  cmd_vel_timeout:=0.5
```

| Argument | Default | Description |
| --- | --- | --- |
| `port_name` | `can0` | SocketCAN interface |
| `omni` | `false` | Enable lateral velocity for SCOUT MINI OMNI |
| `odom_frame` | `odom` | Parent frame for odometry and TF |
| `base_frame` | `base_link` | Robot body frame |
| `odom_topic_name` | `odom` | Odometry topic name |
| `control_rate` | `50` | Hardware command and state loop rate in Hz |
| `cmd_vel_timeout` | `0.5` | Maximum command age before zero velocity, in seconds |
| `use_sim_time` | `false` | Use the ROS simulation clock |

## ROS interface

Driver topics use relative names for namespaces and remapping. TF is published
on `/tf`; use TF remapping and distinct frame names for multi-robot deployments.

### Subscribed topics

| Topic | Type | Description |
| --- | --- | --- |
| `cmd_vel` | `geometry_msgs/msg/Twist` | Longitudinal and angular velocity; `linear.y` is used only by OMNI |
| `light_control` | `scout_msgs/msg/ScoutLightCmd` | Front and rear light mode and brightness |

### Published topics

| Topic | Type | Description |
| --- | --- | --- |
| `scout_status` | `scout_msgs/msg/ScoutStatus` | Motion, battery, errors, lights and four actuator states |
| `odom` | `nav_msgs/msg/Odometry` | Wheel-integrated planar odometry |
| `rc_status` | `scout_msgs/msg/ScoutRCState` | Remote switches, sticks and knob |
| `/tf` | `tf2_msgs/msg/TFMessage` | `odom` to `base_link` transform |

The actuator array order is front-right, front-left, rear-right, rear-left.
Odometry is integrated from base feedback and is not a globally corrected pose.

## Terminal dashboard

The package installs a terminal dashboard alongside the driver:

```bash
ros2 run scout_base scout_test_tui
```

It monitors CAN and ROS data without commanding motion until the operator
explicitly presses uppercase `E`. `Space`, `Esc`, and normal program exit send a
zero command. This tool supports commissioning; it does not replace the
physical emergency stop or an appropriate test enclosure.

The dashboard shows CAN interface state, topic rates and freshness, command
subscriber count, battery voltage, error flags, motor telemetry, odometry,
lights, and remote-control inputs.

| Key | Action |
| --- | --- |
| `E` (uppercase) | Arm or lock motion output |
| `w` / `s` | Short forward / reverse deadman pulse |
| `a` / `d` | Short left / right turn pulse |
| `j` / `l` | Strafe left / right when started with `--omni` |
| `Space` or `Esc` | Send zero velocity and lock |
| `1` / `2` | Toggle front / rear light |
| `q` | Send zero speed and quit |

Drive keys send 0.25 s pulses and must be tapped or held to continue moving.
This is independent of the driver's watchdog. Default speeds are 0.15 m/s
longitudinally and laterally, and 0.35 rad/s for rotation. For an OMNI base at
lower test speeds:

```bash
ros2 run scout_base scout_test_tui --omni \
  --linear-speed 0.08 --lateral-speed 0.08 --angular-speed 0.20
```

Namespaced deployments can remap the console in the normal ROS 2 way:

```bash
ros2 run scout_base scout_test_tui --ros-args \
  -r scout_status:=/robot/scout_status \
  -r odom:=/robot/odom \
  -r rc_status:=/robot/rc_status \
  -r cmd_vel:=/robot/cmd_vel \
  -r light_control:=/robot/light_control
```

## CAN diagnostics

The package also provides a SCOUT MINI diagnostic node:

```bash
ros2 run scout_base scout_mini_smoke --ros-args -p can_interface:=can0
```

By default, it reads state and requests controller and driver versions.
It sends zero-speed commands on exit, so run it without another active motion
controller.

To run the low-speed motion sequence, put the robot on blocks, clear its motion
envelope, and keep the physical emergency stop within reach:

```bash
ros2 run scout_base scout_mini_smoke --ros-args \
  -p can_interface:=can0 -p run_motion_test:=true
```

The sequence enables CAN commanded mode, moves forward, stops, rotates, and
stops again. On exit it sends zero-speed commands without selecting standby.
The executable is provided by `scout_base`; use this package name in place of
`agilex_ugv_sdk` when updating existing diagnostic commands.

## Robot description

`scout_description` contains the SCOUT V2 model with fixed wheel joints. Its
geometry is not a calibrated SCOUT MINI or OMNI model. Applications that use
collision geometry or wheel animation should supply a model for their vehicle.

## Troubleshooting

**The driver reports `failed to open CAN transport`.** Check that the adapter
exists and is up with `ip link show can0`. Confirm the bitrate is 500000 and
that your user has permission to open the interface.

**The TUI shows `NO DATA`.** Confirm the driver is running and that both
terminals use the same ROS distribution and `ROS_DOMAIN_ID`. Run
`ros2 topic hz /scout_status` to separate a ROS discovery problem from a
terminal-display problem.

**The TUI is online but the robot does not move.** The console must show
`Motion: ARMED` and a non-zero `cmd_vel subscribers` count. Also check the
physical emergency stop, robot power, CAN control mode, and `scout_status`
error flags.

**The robot moves briefly and stops.** Both the TUI deadman pulse and the driver
watchdog are working as designed. Hold or repeatedly tap the drive key, and do
not increase either timeout as a substitute for fixing slow or missing command
delivery.
