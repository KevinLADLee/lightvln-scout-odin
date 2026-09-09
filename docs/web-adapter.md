# Web and ROS interfaces

The browser connects to the robot's Web service; the robot's VLN client connects to GPU inference. This reference describes image previews, control behavior, and the interfaces available in the default stack. See the [main README](../README.md) for deployment.

## Inference image and preview

Default preprocessing:

`camera → centered 7:4 crop → 448×256 JPEG → VLN client → inference service`

Raw and compressed camera inputs use the same crop-before-resize pipeline, preserving aspect ratio. For example, a 1600×1296 input uses a centered 1596×912 crop. Match the output dimensions to the deployed model; cropping reduces the visible field of view.

For a different checkpoint, override `image_width`, `image_height`, and `image_fit` consistently under `vln_client` and `vln_web` in the machine preset. Defaults are 448, 256, and `center_crop`; `stretch` enables direct stretching. The defaults correspond to model input height×width of 256×448.

The preview label identifies which image is shown:

| Label | Image shown | Update timing |
| --- | --- | --- |
| `CAMERA` | Idle camera preview, using the model's crop and resize settings | Camera preview rate |
| `VLN INPUT` | Exact JPEG submitted for a completed inference request | Once each inference response completes |

Inference input images are published on `vln/input_image/compressed` with their capture timestamp. The browser overlays pointing markers only when the image and response timestamps match. The `VLN INPUT` preview therefore includes inference latency.

## Console behavior

- Only one browser owns manual or automatic control at a time.
- Manual speed changes are applied atomically to the Scout adapter before the page accepts them. MPC parameters are adjusted while control is inactive.
- **STOP** stops and releases ownership without latching an emergency stop.
- **Software emergency stop** may be requested by an observer without ownership. The adapter latches the stop and rejects new ownership requests.
- **Reset software stop** requires released browser ownership and is rejected while the external emergency topic remains asserted. Reset clears buffered commands and leaves control disabled; it does not resume a task.

Set `scout_adapter.ros__parameters.hardware_output_enabled` in the parameter YAML. When `false`, the page displays a physical output lock. This setting is fixed at launch; inference and MPC can still be inspected with the lock active.

## Telemetry and freshness

The adapter forwards battery voltage in volts, raw vehicle state, control mode, and fault code from `scout_msgs/ScoutStatus`. It does not estimate battery percentage. IMU and motor health remain `UNKNOWN` because the message does not establish those conditions.

`status_timeout_s` defaults to 2 seconds. Expired telemetry is not displayed as valid current state. `ScoutStatus` has no per-CAN-frame timestamps or validity flags, so ROS reception freshness cannot establish CAN health.

After 3 seconds without adapter diagnostics, the Web service marks the adapter unavailable, clears stale telemetry, releases browser ownership, and requests controller stop. The adapter also has an independent command watchdog with a default timeout of 0.35 seconds.

Odin odometry is pushed to browsers at up to 10 Hz, while runtime snapshots retain the latest value. MPC input and control frequency are unaffected.

## HTTP and WebSocket

The Web port defaults to `8088` and is configurable with `vln_web.ros__parameters.port` in the parameter YAML.

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Browser console |
| `GET /api/health` | Runtime snapshot containing `robot`, `vln`, and `mpc` |
| `GET /api/camera.jpg` | Latest camera preview |
| `GET /ws` | Browser command and status WebSocket |

For example, a browser software-stop request is:

```json
{"type": "robot_action", "action": "emergency_stop"}
```

The server forwards supported actions to ROS services and returns `command_result`. State is sent separately through `robot_diagnostics` and periodic `runtime` messages. Check both the result and the reported latch state; receiving a WebSocket message alone does not prove the base has stopped.

The HTTP/WebSocket service provides neither user authentication nor TLS. Use it on a trusted robot network or behind a configured gateway.

## ROS topics

The table retains relative names from the interface definitions. Relative names resolve under the root namespace in the default configuration.

| Topic | Type | Purpose |
| --- | --- | --- |
| `vln/input_image/compressed` | `sensor_msgs/CompressedImage` | Actual completed inference input with capture timestamp |
| `vln/response` | `std_msgs/String` | Inference JSON with image capture timestamp |
| `vln/path_body` | `nav_msgs/Path` | Model output in the body frame |
| `vln/path_odom` | `nav_msgs/Path` | Capture-time-aligned odometry-frame path |
| `mpc/cmd_vel` | `geometry_msgs/TwistStamped` | Automatic velocity command |
| `web/cmd_vel` | `geometry_msgs/TwistStamped` | Browser manual velocity command |
| `/lightvln_scout/cmd_vel_sent` | `geometry_msgs/TwistStamped` | Velocity command after adapter gates |
| `/cmd_vel` | `geometry_msgs/Twist` | Final velocity command sent to the Scout driver |
| `/scout_status` | `scout_msgs/ScoutStatus` | Scout base telemetry |
| `diagnostics` | `diagnostic_msgs/DiagnosticArray` | `robot_adapter` state and capabilities |
| `control/source` | `std_msgs/String` | `disabled`, `manual`, or `auto` |
| `mpc/status` | `std_msgs/String` | Controller state |
| `mpc/reference`, `mpc/prediction` | `nav_msgs/Path` | Controller visualization |
| `/lightvln_scout/emergency_stop` | `std_msgs/Bool` | External software stop: `true` latches; `false` clears the external assertion, but the latch still requires reset |

## ROS services

| Service | Type | Purpose |
| --- | --- | --- |
| `control/set_manual`, `control/set_auto` | `std_srvs/SetBool` | Select or disable the corresponding control source |
| `control/stop` | `std_srvs/Trigger` | Disable control |
| `robot/emergency_stop` | `std_srvs/Trigger` | Latch software stop |
| `robot/reset_emergency_stop` | `std_srvs/Trigger` | Clear the stop latch without resuming control |

The integration executables `scout_vln_client` and `scout_vln_web` run as ROS nodes `vln_client` and `vln_web`, reusing upstream transport and Web/ROS controls. For implementation details, see the [VLN client](../src/lightnav/vln_client/README.md) and [MPC controller](../src/lightnav/vln_mpc/README.md).
