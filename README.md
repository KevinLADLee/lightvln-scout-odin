# LightVLN Scout

A ROS 2 workspace for running a LightNav-compatible vision-language navigation
pipeline on a Scout Mini with an Odin1 sensor. It includes a browser interface,
a capture-time-aligned MPC controller, and a Scout command and telemetry adapter.

The inference server and model weights are **not included**. Configure a separate
server implementing the LightNav WebSocket protocol to run navigation tasks.
You can build the workspace and inspect the web interface without a robot or
an inference server.

## Architecture

```text
Odin RGB image ──> vln_client <──WebSocket──> inference server
                       │
                  vln/response
                       ▼
Odin odometry ──> vln_mpc ──> mpc/cmd_vel ──┐
                                          ▼
browser <──> vln_web ──> web/cmd_vel ──> scout_adapter ──> /cmd_vel
                ▲                         │                  │
                └────── diagnostics ──────┘             Scout driver
                                          ▲                  │
                                          └── /scout_status ─┘
```

The adapter owns manual/automatic arbitration, command expiry, speed validation,
and software emergency stop. Hardware motion output is disabled by default.

## Requirements

- Linux with ROS 2 Humble and its matching system Python. The workspace targets
  Ubuntu 22.04; other ROS distributions have not been validated here.
- C/C++ build tools, CMake, `colcon`, and initialized `rosdep`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) on your `PATH`.
- For hardware use: Scout Mini with a configured SocketCAN interface, Odin1
  with the required USB permissions, and a reachable compatible inference server.
- Optional: NetworkManager and `nmcli` for the web Wi-Fi panel; SSH and `rsync`
  for remote deployment.

Install ROS using the [ROS 2 Humble installation guide](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html).
The Python overlay retains ROS system packages; do not replace the system Python
with an unrelated Python or Conda environment. Python dependencies are listed in
[requirements.txt](requirements.txt) and [requirements-dev.txt](requirements-dev.txt).

## Get started

Replace `<repository-url>` with this project's clone URL. All commands below
run from the checkout root; its location and directory name are your choice.

```bash
git clone <repository-url> lightvln-scout
cd lightvln-scout
./scripts/bootstrap.bash --rosdep
source scripts/env.bash
```

For Zsh, use `source scripts/env.zsh`. Bootstrap creates `.venv`, installs the
Python overlay, resolves system dependencies with `--rosdep`, and builds the
workspace. Omit `--rosdep` if dependencies are already installed. Use
`--no-build` to prepare only the environment, then `./scripts/build.bash` to build.

### Inspect the interface without hardware

```bash
ros2 launch lightvln_scout controller_only.launch.py \
  launch_scout_base:=false \
  require_output_subscriber:=false \
  motion_enabled:=false
```

Open `http://localhost:8088` on the host running the launch. From another computer,
replace `localhost` with that host's reachable address. In this mode, camera and
telemetry remain unavailable until their publishers are present. The adapter's
connected indicator represents the bench configuration, not a detected robot.
Navigation requires camera images, odometry, and an inference server.

The server URL is empty by default. Set it on the page or pass
`server_url:=ws://<inference-host>:<port>` to the launch. The URL is resolved from
the robot computer; the browser does not connect directly to the inference server.

### Connect a robot

Follow [Hardware configuration](docs/hardware.md) to configure CAN, sensor topics,
coordinate frames, and measured sensor mounting offsets. Start with
`motion_enabled:=false` to inspect the pipeline before enabling physical output.

`controller_only.launch.py` starts the LightNav components and the adapter, with
an optional Scout driver. `scout_odin.launch.py` also starts the Odin driver and
its RViz window. Do not launch a second instance of a driver that is already running.

## Web interface and adapter

The page supports camera preview, trajectory overlays, navigation start/stop,
manual control ownership, speed limits, MPC tuning, and Scout telemetry.
Unsupported legged-robot actions are hidden. Battery voltage is shown in volts;
unknown charge percentage is not reported as zero.

See [Web adapter and ROS interfaces](docs/web-adapter.md) for message contracts,
software emergency stop/reset behavior, telemetry expiry, and limitations.
The built-in HTTP/WebSocket server has no user authentication or TLS termination;
use it on a trusted robot network or behind an appropriately configured gateway.

## Build and test

```bash
./scripts/build.bash
ROS_DOMAIN_ID=199 ROS_LOCALHOST_ONLY=1 ./scripts/test.bash
```

Build first so generated `scout_msgs` interfaces are available. `199` is an
example test domain: choose one unused by other local ROS applications.
`ROS_LOCALHOST_ONLY=1` restricts discovery to the local computer. Runtime components
that need to communicate must use the same `ROS_DOMAIN_ID`; no project-specific
domain is required.

The test script runs lint and Python regression tests, including an in-process
HTTP/WebSocket test. Passing these tests does not validate hardware calibration
or robot motion. After source edits, rebuild and restart affected nodes.

## Remote deployment

The target must be supplied explicitly. These are placeholders, not defaults:

```bash
LIGHTNAV_DEPLOY_HOST='<user>@<robot-host>' \
LIGHTNAV_DEPLOY_ROOT='lightvln-scout' \
  ./scripts/deploy_robot.bash
```

A relative destination is resolved under the remote user's home directory; an
absolute destination may also be supplied. The script uses your SSH configuration
and key authentication. Add `--ask-password` for interactive password entry
(requires `sshpass`). Run `./scripts/deploy_robot.bash --help` for accepted values.

Deployment copies source only, excluding build outputs, caches, local settings,
and backups. It does not install dependencies, build, restart services, or remove
unrelated remote files. On the target, install the prerequisites, enter the
transferred directory, and run `./scripts/bootstrap.bash --rosdep`.

## Repository layout and upstream code

| Directory | Contents |
| --- | --- |
| `src/lightnav/` | LightNav-derived `vln_client`, `vln_mpc`, and `vln_web` |
| `src/integration/lightvln_scout/` | Scout adapter, launch files, and configuration |
| `src/drivers/` | Vendored Odin and Scout drivers, including the Scout SDK |
| `scripts/` | Environment, build, test, and deployment tools |
| `docs/` | Hardware setup and adapter reference |

Colcon discovers packages recursively. The driver snapshots retain upstream
licenses and `UPSTREAM_VERSION` files recording their source revisions; use
those records when updating vendored code. Package licensing is recorded in
`package.xml` and the accompanying upstream license files. See
[Licensing and third-party code](LICENSES.md) for the repository-level map.

Keep machine-specific notes, addresses, and settings in `.local/` or outside
the checkout. `.local/` and `.backups/` are ignored by Git and excluded from the
deployment script. Preserve upstream attribution when contributing changes.

Odin runtime artifacts are kept outside the checkout under
`~/.ros/odin_ros_driver/` by default. Set `ODIN_RUNTIME_DIR` to relocate logs,
maps, recordings, and the default calibration file. Set `ODIN_CALIB_DIR` or
`ODIN_DATA_DIR` only when calibration or recordings need separate locations.

Image cropping and inference-aligned previews are owned by the Scout integration.
See [image pipeline and configuration](docs/web-adapter.md#inference-image-and-preview).

## Vendored dependency versions

All third-party dependencies are committed as ordinary files. This repository
does not use Git submodules.

| Component | Upstream revision | Notes |
| --- | --- | --- |
| [Manifold Odin ROS driver](https://github.com/manifoldsdk/odin_ros_driver) | [`a592cf2`](https://github.com/manifoldsdk/odin_ros_driver/commit/a592cf2cc08bc8bfb0dceae44ef31f3a6bd77822) | Includes project-specific configuration and runtime-path changes |
| [Scout ROS 2](https://github.com/Hive-Matrix-AI/scout_ros2) | [`165083d`](https://github.com/Hive-Matrix-AI/scout_ros2/commit/165083d93942955870a96bd1b984a7b9f6f4fcdd) | Snapshot of the upstream `humble` branch |
| [AgileX UGV SDK](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk) | [`c3fa0c9`](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk/commit/c3fa0c92144dda542c45b12b7bf3c0ba8e635159) | Vendored under `src/drivers/scout_ros2/third_party/` |
