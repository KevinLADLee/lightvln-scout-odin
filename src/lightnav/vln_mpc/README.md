# vln_mpc

VLN trajectory pose alignment and MPC control node.

Requires CasADi `>=3.7,<4` at runtime.

## Interface

| Name | Type | Direction | Description |
| --- | --- | --- | --- |
| `vln/response` | `std_msgs/String` | subscribe | JSON inference result; waypoints are in the `base_link` frame at image capture time |
| `vln/status` | `std_msgs/String` | subscribe | VLN state: `IDLE`, `RUNNING`, or `ERROR` |
| `vln/mode` | `std_msgs/String` | subscribe | Task mode: `objnav` or `track`; Transient Local |
| `mpc/enable` | `std_msgs/Bool` | subscribe | `true` enables MPC, `false` disables it; Reliable, Volatile, depth 1 |
| `odom` | `nav_msgs/Odometry` | subscribe | `odom`-to-`base_link` pose and timestamp |
| `mpc/cmd_vel` | `geometry_msgs/TwistStamped` | publish | Linear and angular velocity output by the MPC |
| `vln/path_odom` | `nav_msgs/Path` | publish | Raw VLN waypoints aligned into `odom`; Transient Local |
| `mpc/reference` | `nav_msgs/Path` | publish | Pose-aligned reference trajectory used by the tracking MPC |
| `mpc/prediction` | `nav_msgs/Path` | publish | MPC predicted trajectory |
| `mpc/status` | `std_msgs/String` | publish | `IDLE` (disabled), `RUNNING` (enabled), or `ERROR`; published on state change, Transient Local |

## Notes

The node keeps a recent odom history and looks up the robot pose at image capture
time by `capture_stamp_ns`, transforming the body-frame waypoints in
`vln/response` into `odom`.

The tracking MPC runs at `10 Hz`. On every solve it picks the discrete waypoint
closest to the current robot pose, weighting the pose error by `q_x`, `q_y`, and
`q_yaw`, then takes `horizon` points starting from the next one, repeating the
last point when there are not enough. It then builds a fixed local frame at the
current robot pose, normalizing the current state to `[0, 0, 0]`; the `state[k+1]`
produced by the `k`-th control tracks the `k`-th reference point. Each solve
seeds the control initial guess from the finite-difference velocities of the
current reference and rolls out the state initial guess with a unicycle model —
the previous cycle's solution is not reused. The MPC constrains linear velocity,
angular velocity, linear acceleration, and angular acceleration. Reference and
prediction trajectories are still published in `odom`.

The control rate is fixed at `10 Hz`, the horizon at `5`, and the MPC and
waypoint time step at `0.1 s`. The remaining MPC parameters are configured by
each robot's launch file.

`q_x`, `q_y`, `q_yaw`, `r_v`, `r_w`, the velocity/acceleration constraints, and
the output scales support hot reload through the ROS 2 parameter service.
Parameters can only be changed while MPC is disabled and the current solve has
finished; the web page locks the MPC parameter panel while VLN/MPC is running.
Changes are not written back to the launch file — a node restart restores the
robot's launch configuration. `v_output_scale` and `w_output_scale` multiply
the linear and angular velocity outputs respectively, after the MPC solve and
constraints.

The task mode is independent of the MPC control mode above. `track` ignores the
VLN `stop` flag; `objnav` immediately invalidates the current solve and stops
publishing velocities when `stop=true`. `vln_web` reads the same VLN response
directly, disables MPC, releases automatic control, and stops VLN requests.

The node publishes `mpc/cmd_vel` only after a successful MPC solve. It publishes
no velocity while disabled, waiting for input, on stale odom, or on solver
failure; stopping, control-source selection, and the command watchdog are the
robot adapter's responsibility. The specific wait reasons, errors, and solve
times are recorded in the logs.

## Default parameters

| Parameter | Default |
| --- | --- |
| `enabled` | `false` |
| `odom_frame` / `base_frame` | `odom` / `base_link` |
| `track_v_max` / `objnav_v_max` | `1.5 m/s` / `0.8 m/s` |
| `w_max` | `3.0 rad/s` |
| `a_max_v` / `a_max_w` | `2.0 m/s²` / `5.0 rad/s²` |
| `q_x` / `q_y` / `q_yaw` | `10.0` / `10.0` / `1.0` |
| `r_v` / `r_w` | `0.1` / `0.1` |
| `v_output_scale` / `w_output_scale` | `1.0` / `1.0` |
| `odom_match_max_gap_s` | `0.3 s` |
| `odom_timeout_s` | `0.5 s` |
| `metrics_log_period_s` | `2.0 s` |

## Layout

- `mpc_node.py`: ROS interface, pose alignment, and the control loop.
- `geometry.py`: odom interpolation and coordinate transforms.
- `mpc.py`: pose reference construction and the trajectory-tracking MPC.
