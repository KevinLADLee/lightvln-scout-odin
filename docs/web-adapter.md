# Web adapter and ROS interfaces

`lightvln_scout` launches its own `scout_vln_client` and `scout_vln_web` adapters.
They reuse the original VLN transport, ROS controls, and HTTP/WebSocket services.
The integration owns image processing, browser assets, Scout command gates, and
telemetry translation. The browser does not connect to ROS or the inference server directly.

## Inference image and preview

The integration's default pipeline is:

`camera → centered 7:4 crop → 448×256 JPEG → original VLN transport → server`

`ImagePreprocessor` in `lightvln_scout/image_processing.py` handles both raw and
compressed input. It crops before resizing, so horizontal and vertical scales
are equal. For example, a 1600×1296 image uses a centered 1596×912 crop. Cropping
reduces the visible field of view; choose dimensions to match your deployed
model's preprocessing, not the camera's native resolution.

Configure `image_width`, `image_height`, and `image_fit` under both `vln_client`
and `vln_web` in `config/standard_stack.yaml`. Defaults are 448, 256, and
`center_crop`; `stretch` explicitly enables legacy stretching. These defaults
match a model with fixed 256×448 (height×width) input. Other servers may use a
different aspect ratio or dynamic sizing, so check their model configuration.

During inference, the client adapter publishes the **exact submitted JPEG** on
`vln/input_image/compressed` when its response completes. The web adapter serves
those bytes directly. The preview therefore advances at completed-inference
cadence, with inference latency, and is not a separate live camera stream.
Image and response capture timestamps are compared as strings in the browser;
pointing overlays appear only on their matching input frame. The canvas uses
the JPEG's actual dimensions. `VLN INPUT` identifies submitted frames; `CAMERA`
identifies idle previews processed using the same crop and resize configuration.

The original client, client node, and web node expose optional encoder/factory
arguments. Their standalone defaults remain unchanged. No inference-server,
model, response protocol, or MPC changes are required. Integration browser
assets live in `lightvln_scout/web` rather than modifying the original web app.

## Browser behavior

- One browser can own manual or automatic control at a time.
- Manual speed changes are applied atomically to the Scout adapter before the
  page accepts them. MPC tuning is available while control is inactive.
- Stand/Walk/Crouch/Policy buttons are hidden when the adapter does not advertise
  those actions. The compatibility `WALK` state means the wheeled base is ready
  for this control interface, not that it has a legged locomotion mode.
- **STOP** stops and releases control without latching.
- **Software emergency stop** can be requested by an observer without ownership.
  The adapter latches the stop and rejects subsequent control acquisition.
- **Reset software stop** requires released browser control and is rejected while
  the external emergency topic remains asserted. Reset clears buffered commands
  and leaves control disabled; it does not resume navigation.

`hardware_output_enabled=false` is displayed as an output lock. This setting is
fixed at launch. A dry run may exercise inference and MPC with this lock applied.

## Telemetry and freshness

The Scout telemetry adapter forwards battery voltage in volts and raw vehicle
state, control mode, and fault code from `scout_msgs/ScoutStatus`. It does not
estimate battery percentage. IMU and motor health remain `UNKNOWN` because the
message does not establish their validity.

`status_timeout_s` defaults to 2 seconds. Expired data is not displayed as current
telemetry. Reception freshness describes the ROS publisher; `ScoutStatus` has no
per-CAN-frame timestamps or validity flags, so it cannot establish CAN health.

If adapter diagnostics stop for 3 seconds, the web server marks the adapter
unavailable, clears stale telemetry, releases browser ownership, and requests
controller stop. The adapter's independent command watchdog defaults to 0.35 s.
Odin odometry is pushed to browsers at up to 10 Hz, while snapshots retain the
latest sample. MPC input and control frequency are unaffected.

## HTTP and WebSocket

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Browser application |
| `GET /api/health` | Current runtime snapshot, including `robot`, `vln`, and `mpc` |
| `GET /api/camera.jpg` | Latest camera preview |
| `GET /ws` | Browser command and status WebSocket |

The port defaults to 8088 and can be changed with the launch argument `web_port`.
For example, a client may send:

```json
{"type": "robot_action", "action": "emergency_stop"}
```

The server forwards a supported action to its ROS service and returns a
`command_result`. Status arrives separately as `robot_diagnostics` and periodic
`runtime` messages. Check the result and reported latch state; receipt of a
WebSocket message alone does not prove that the robot stopped.

## ROS topics

| Topic | Type | Purpose |
| --- | --- | --- |
| `vln/input_image/compressed` | `sensor_msgs/CompressedImage` | Exact completed inference input, with capture stamp |
| `vln/response` | `std_msgs/String` | Inference JSON with image capture timestamp |
| `vln/path_body` | `nav_msgs/Path` | Body-frame model output |
| `vln/path_odom` | `nav_msgs/Path` | Capture-time-aligned odometry-frame path |
| `mpc/cmd_vel` | `geometry_msgs/TwistStamped` | Autonomous command |
| `web/cmd_vel` | `geometry_msgs/TwistStamped` | Browser manual command |
| `/lightvln_scout/cmd_vel_sent` | `geometry_msgs/TwistStamped` | Command after adapter gates |
| `/cmd_vel` | `geometry_msgs/Twist` | Final Scout driver command |
| `/scout_status` | `scout_msgs/ScoutStatus` | Scout driver telemetry |
| `diagnostics` | `diagnostic_msgs/DiagnosticArray` | `robot_adapter` status and capabilities |
| `control/source` | `std_msgs/String` | `disabled`, `manual`, or `auto` |
| `mpc/status` | `std_msgs/String` | Controller state |
| `mpc/reference`, `mpc/prediction` | `nav_msgs/Path` | Controller visualization |
| `/lightvln_scout/emergency_stop` | `std_msgs/Bool` | External software latch (`true`) / clear (`false`) |

## ROS services

| Service | Type | Purpose |
| --- | --- | --- |
| `control/set_manual`, `control/set_auto` | `std_srvs/SetBool` | Select or disable command ownership |
| `control/stop` | `std_srvs/Trigger` | Disable control |
| `robot/emergency_stop` | `std_srvs/Trigger` | Latch software stop |
| `robot/reset_emergency_stop` | `std_srvs/Trigger` | Clear software stop without resuming control |

For lower-level details, see the [VLN client](../src/lightnav/vln_client/README.md)
and [MPC controller](../src/lightnav/vln_mpc/README.md) documentation.
