# Hardware configuration

This guide covers Scout Mini and Odin1 configuration on the robot. See the [main README](../README.md) for the deployment sequence and [server setup](../README.md#1-deploy-the-gpu-server) for inference setup.

Run commands from this repository root after sourcing `scripts/env.bash`, or `scripts/env.zsh` for Zsh.

## Parameter presets

Both launch files read [standard_stack.yaml](../src/integration/lightvln_scout/config/standard_stack.yaml). It contains the server address, CAN interface, mounting offsets, and physical output switch. Image, interface, and MPC settings load automatically from [defaults.yaml](../src/integration/lightvln_scout/config/defaults.yaml) and node defaults.

For a machine-specific preset, create a local copy:

```bash
mkdir -p .local
cp src/integration/lightvln_scout/config/standard_stack.yaml .local/robot.yaml
```

Edit `.local/robot.yaml`, then launch with that file:

```bash
ros2 launch lightvln_scout scout_odin.launch.py params_file:="$PWD/.local/robot.yaml"
```

The selected file overlays the robot preset and may contain only the sections and parameters being changed. Advanced overrides use the corresponding node's `ros__parameters`, for example `vln_mpc` for MPC or `vln_web` for the Web port. Restart after editing. Explicit launch arguments remain available for temporary overrides.

## Devices and topics

| Input or interface | Default | Configuration |
| --- | --- | --- |
| RGB image | `/odin1/image/undistorted`, raw `bgr8` or `rgb8` | `vln_client.image_topic` and `vln_web.image_topic` |
| Odometry | `/odin1/odometry_highfreq`, `odom` → `imu` | `vln_web.odom_topic` and `vln_mpc.odom_topic` |
| Scout velocity command | `/cmd_vel`, `geometry_msgs/Twist` | `scout_adapter.output_topic` |
| Scout telemetry | `/scout_status` | `scout_adapter.status_topic` |
| CAN interface | `can0` | `robot_launch.scout_port` in `standard_stack.yaml` |

For a custom sensor setup, add overrides under the corresponding node's `ros__parameters` in your machine preset. Update both client and Web nodes when changing image topics, and both MPC and Web nodes when changing odometry topics. Restart nodes after configuration changes.

Configure SocketCAN and the bitrate for the actual base using the [Scout driver instructions](../src/drivers/scout_ros2/README.md).

Follow the [Odin driver instructions](../src/drivers/odin_ros_driver/README.md) for USB permissions and sensor parameters. Images and odometry must share a compatible time base so MPC can match poses to image capture times.

`scout_odin.launch.py` includes the Odin driver's RViz window. For headless deployment, start the required driver nodes separately and use `controller_only.launch.py`.

## Measure sensor mounting offsets

Both integration launches publish the static transform `imu` → `base_link`. Set the following under `robot_launch.ros__parameters`:

| Parameters | Meaning | Unit |
| --- | --- | --- |
| `imu_to_base_x/y/z` | Position of the `base_link` origin expressed in the `imu` frame | Metres |
| `imu_to_base_roll/pitch/yaw` | Orientation of `base_link` relative to `imu` | Radians |

Use measured values; zero offsets are only a bench preset. MPC uses the same x, y, and yaw offsets for planar tracking.

Supply every mounting offset before operating hardware. Resolve duplicate publishers if another node already publishes this TF.

## First run with physical output disabled

With both drivers already running, keep `hardware_output_enabled: false` in the robot preset and run:

```bash
ros2 launch lightvln_scout controller_only.launch.py
```

If only Odin is running, add `controller_only.ros__parameters.launch_scout_base: true` to the machine preset to start Scout. If neither driver is running, use `scout_odin.launch.py`. Add `params_file` when using a separate machine preset.

Open `http://<robot-host>:8088` and check images, odometry frames, the inference URL, and diagnostics. Verify the model path on the GPU server. With `hardware_output_enabled: false`, tasks can exercise inference and MPC while the adapter forces final velocity commands to zero.

## Enable motion after validation

1. Verify mounting transforms and trajectory directions in RViz or recorded data.
2. Use `ros2 topic info /cmd_vel` to confirm the intended Scout driver subscribes to the output topic.
3. Check base telemetry and the physical stopping mechanism.
4. Secure the robot with its wheels off the ground. Retain measured offsets and subscriber checking, set `scout_adapter.ros__parameters.hardware_output_enabled: true` in the YAML, and relaunch.
5. Validate low-speed manual control, stopping, and emergency-stop reset before testing automatic tracking in an open area. Resetting software stop leaves control disabled; start a new control session explicitly.

Default speed limits are an initial configuration. Review `max_linear_speed`, `max_angular_speed`, and MPC limits for the actual base. Console adjustments cannot exceed the adapter's launch-time speed ceilings. Software emergency stop does not replace hardware emergency stop.

## Troubleshooting

| Symptom | Checks |
| --- | --- |
| No camera image | Driver state, image topic and transport, publisher QoS, ROS domain |
| Odometry cannot be matched | Frame names, time base, and image/odometry timestamp difference |
| Adapter disconnected | Scout driver subscriber, `/cmd_vel` remapping, ROS domain |
| Connected but no motion | Physical output lock, emergency latch, ownership, command freshness, speed limits |
| Telemetry unavailable | `/scout_status` publisher and configured topic; data expires after 2 seconds by default |
| Wi-Fi panel unavailable | Optional NetworkManager/`nmcli` installation and permissions |

An output subscriber does not establish CAN health. Use driver diagnostics to investigate base communication problems.
