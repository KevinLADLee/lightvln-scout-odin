# Hardware configuration

Run commands from the checkout root after sourcing `scripts/env.bash` (or
`scripts/env.zsh`). Replace angle-bracket placeholders before executing examples.

## Configure your devices

The provided integration configuration expects:

| Input | Default | Configuration |
| --- | --- | --- |
| RGB image | `/odin1/image/undistorted`, raw `bgr8` or `rgb8` | `vln_client` and `vln_web` in `config/standard_stack.yaml` |
| Odometry | `/odin1/odometry_highfreq`, `odom` → `imu` | `vln_web` in `standard_stack.yaml`; `vln_mpc` in `upstream_mpc.yaml` |
| Scout command | `/cmd_vel`, `geometry_msgs/Twist` | `scout_adapter.output_topic` in `standard_stack.yaml` |
| Scout telemetry | `/scout_status` | `scout_adapter.status_topic` in `standard_stack.yaml` |
| CAN interface | `can0` | Launch argument `scout_port` |

Configuration paths above are relative to
`src/integration/lightvln_scout/`. Align both image consumers and both odometry
consumers when changing topics. Rebuild after editing package configuration.

Configure the SocketCAN interface and bitrate for your particular Scout hardware,
using the [Scout driver instructions](../src/drivers/scout_ros2/README.md).
This workspace does not configure CAN automatically or assume an existing
interface is ready. The optional Scout driver publishes separate wheel odometry
on `/scout/wheel_odom` with frames `scout_wheel_odom` → `scout_wheel_base`.
Odin remains the authoritative odometry source for navigation.

Follow the [Odin driver instructions](../src/drivers/odin_ros_driver/README.md)
for USB permissions and sensor configuration. Camera images and odometry must
use compatible timestamps so MPC can look up the pose at image capture time.
The full launch includes the driver's RViz window; for headless use, start the
required driver nodes separately and use `controller_only.launch.py`.

## Measure sensor mounting offsets

Both integration launches publish `imu` → `base_link`. Configure the transform
for your own mounting arrangement using `imu_to_base_x/y/z` (metres) and
`imu_to_base_roll/pitch/yaw` (radians). The public defaults are an identity
transform for bench inspection, **not a robot calibration**. MPC uses the same
x/y/yaw offset to convert the odometry child pose into the control frame.

Supply all measured offsets when operating hardware. If another node already
publishes this transform, resolve the duplicate publisher before launching.

## First run with physical output disabled

If the Odin driver is already running and the Scout driver is not:

```bash
ros2 launch lightvln_scout controller_only.launch.py \
  server_url:=ws://<inference-host>:<port> \
  launch_scout_base:=true \
  scout_port:=<can-interface> \
  require_output_subscriber:=true \
  motion_enabled:=false \
  imu_to_base_x:=<x-metres> \
  imu_to_base_y:=<y-metres> \
  imu_to_base_z:=<z-metres> \
  imu_to_base_roll:=<roll-radians> \
  imu_to_base_pitch:=<pitch-radians> \
  imu_to_base_yaw:=<yaw-radians>
```

If the Scout driver is already running, use `launch_scout_base:=false`. If neither
driver is running, use `scout_odin.launch.py` with the same device and mounting
arguments, omitting `require_output_subscriber` (the full launch always requires
an output subscriber).

Open `http://<robot-host>:8088`. Confirm the image, odometry frames, model path,
and diagnostics. Starting VLN with `motion_enabled:=false` allows inference and
MPC inspection while the adapter forces final commands to zero.

## Enable motion after validation

1. Verify the measured transform and path directions in RViz or recorded data.
2. Confirm `ros2 topic info /cmd_vel` shows the intended Scout driver subscriber.
3. Check hardware telemetry and the robot's physical stopping mechanism.
4. Validate low-speed control with the wheels off the ground before an open-area test.
5. Relaunch with your measured offsets, `motion_enabled:=true`, and subscriber
   checking enabled. Do not use bench settings to bypass the driver check.

The supplied limits are a conservative starting configuration, not a guarantee
for every installation. Review `max_linear_speed`, `max_angular_speed`, and MPC
limits for your robot. Runtime web changes cannot raise adapter speed limits
above the values supplied at launch. The software stop does not replace a
hardware emergency stop.

## Troubleshooting

| Symptom | Checks |
| --- | --- |
| No camera image | Driver running, image topic and transport, publisher QoS, ROS domain |
| No odometry match | Frame IDs, sensor timestamp domain, camera/odometry timing |
| Adapter disconnected | Scout driver subscriber, `/cmd_vel` remapping, ROS domain |
| Connected but no motion | Hardware output lock, emergency latch, control owner, fresh commands and speed limits |
| Telemetry unavailable | `/scout_status` publisher and configured topic; messages expire after 2 seconds by default |
| Wi-Fi panel unavailable | Optional NetworkManager/`nmcli` installation and user permissions |

Connection based on an output subscriber is not proof of a healthy CAN bus.
Use the driver tools for hardware-level inspection.
