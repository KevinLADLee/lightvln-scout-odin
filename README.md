# LightVLN-0 + Scout Mini + Odin1

English | [简体中文](README.zh-CN.md)

This project integrates **LightNav-0 with the Scout Mini mobile base and Odin1 sensor** on a real robot. Model inference runs on a GPU server, while the robot computer runs ROS 2 perception, MPC path tracking, and Scout control. A browser provides operation and monitoring.

Official resources: [LightNav-0 model overview](https://www.lightorigins.com/blog/lightnav-0) · [Scout Mini product page](https://global.agilex.ai/products/scout-mini) · [Odin1 documentation](https://manifoldtechltd.github.io/wiki/odin_series/odin1/)

This repository contains the robot workspace, Odin/Scout drivers, and integration code. **Prepare the inference service and model weights in a separate LightNav-0 checkout.** Start the server before connecting the robot stack.

## Deployment architecture

| Location | Components | Entry point |
| --- | --- | --- |
| GPU server | LightNav-0 model, vLLM inference, LightNav WebSocket service | `ws://<gpu-host>:8050` |
| Robot computer | Odin1 driver, VLN client, MPC, Scout adapter and base driver | ROS 2 launch files in this repository |
| Operator computer | Browser console | `http://<robot-host>:8088` |

![ROS 2 node-topic topology for LightVLN-0, Scout Mini, and Odin1, including perception, inference, MPC, base control, task instructions, and status feedback.](docs/assets/ros-topology.png)

The diagram shows the main connections in the default configuration. See [Web and ROS interfaces](docs/web-adapter.md) for details.

## Integration features

- **Odin1 perception:** supplies camera images and odometry for navigation.
- **Aligned model input and preview:** displays the image submitted for inference with the matching model output.
- **Path tracking and coordinate alignment:** MPC matches odometry to the image capture time and applies the measured `imu` → `base_link` mounting offset.
- **Scout Mini control:** coordinates manual/automatic ownership, command expiry, speed limits, software emergency stop, and telemetry. Physical motion output is disabled by default.
- **Browser console:** provides camera preview, model trajectories, task start/stop, manual control, MPC tuning, and battery voltage.

## 1. Deploy the GPU server

The server needs a separate **LightNav-0 checkout, Python 3.11 environment, CUDA GPU, and model weights**. For initial setup on the GPU host:

```bash
git clone https://github.com/lightorigins/LightNav-0.git
cd LightNav-0
git checkout a645828d81a8439651172197ca80a75dc1377977
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[vllm,video]'
uv run --no-sync hf download LightOriginsHQ/LightNav-0 \
  --local-dir checkpoints/LightNav-0
uv run --no-sync python -c 'import torch; print(torch.cuda.is_available())'
```

The CUDA check should print `True`. Keep upstream dependency constraints and the complete checkpoint, including `eval_config.json` and `action_tokenizer/`. Complete Hugging Face login and model access authorization if downloading requires them. Existing installations can skip setup.

After preparing the environment and weights, start target-following inference from the **LightNav-0 repository root on the GPU server**:

```bash
uv run --no-sync lightnav-serve \
  --task tracking \
  --model_path "$PWD/checkpoints/LightNav-0" \
  --backend vllm_local \
  --gpu_memory_utilization 0.85 \
  --host 0.0.0.0 \
  --port 8050
```

Wait for `[lightnav-ws] READY`, then connect the robot to `ws://<gpu-host>:8050`.

`tracking` selects target following; use `--task vln` for instruction navigation. The console's `track/objnav` modes control robot behavior: `track` continuously follows the path, while `objnav` can complete a task on the model's `stop` signal. They do not change the server's `--task`; restart or switch server instances to change model tasks.

## 2. Prepare the robot computer

The robot stack targets **Ubuntu 22.04 + ROS 2 Humble** and requires the matching system Python, C/C++ build tools, CMake, `colcon`, initialized `rosdep`, and [uv](https://docs.astral.sh/uv/getting-started/installation/). Install ROS using the [ROS 2 Humble guide](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html).

On the robot computer:

```bash
git clone https://github.com/KevinLADLee/lightvln-scout-odin.git
cd lightvln-scout-odin
./scripts/bootstrap.bash --rosdep
source scripts/env.bash
```

For Zsh, use `source scripts/env.zsh`. Bootstrap creates a `.venv` that retains ROS system packages, installs Python dependencies, and builds the workspace. Omit `--rosdep` if system dependencies are already installed. Keep the server's Python 3.11 environment separate from the robot's ROS environment.

Follow [Hardware configuration](docs/hardware.md) to configure Scout SocketCAN, Odin USB permissions, topics, and measured sensor mounting offsets.

## 3. Launch the robot and connect the server

Edit [standard_stack.yaml](src/integration/lightvln_scout/config/standard_stack.yaml), the short robot preset. Set these values under each section's `ros__parameters`:

| Section | Settings |
| --- | --- |
| `vln_client` | `server_url`: `ws://<gpu-host>:8050` |
| `robot_launch` | `scout_port` and all six measured `imu_to_base_*` offsets |
| `scout_adapter` | `hardware_output_enabled`: initially `false` |

With **neither driver already running**, start the full stack:

```bash
ros2 launch lightvln_scout scout_odin.launch.py
```

| Driver state | Launch configuration |
| --- | --- |
| Neither Odin nor Scout is running | Use `scout_odin.launch.py` above; it includes Odin RViz |
| Both drivers are running | Use `controller_only.launch.py` with its default YAML settings |

The inference URL can also be set in the console. For a separate machine preset, use `params_file:=/path/to/robot.yaml`; see [Hardware configuration](docs/hardware.md#parameter-presets).

Open **`http://<robot-host>:8088`** on the operator computer, then:

1. Check the camera, Odin odometry, Scout diagnostics, and inference URL `ws://<gpu-host>:8050`.
2. For a `tracking` server, select `track`, enter a target-following instruction, and start the task.
3. Check server request logs, client connection state, inference latency, and returned trajectories.
4. Inspect inference and MPC with `hardware_output_enabled: false`; final base commands remain zero.
5. Complete [hardware validation](docs/hardware.md#enable-motion-after-validation), then set `hardware_output_enabled: true` in the YAML and relaunch.

To inspect only the interface without hardware, use the default preset:

```bash
ros2 launch lightvln_scout controller_only.launch.py
```

Open `http://localhost:8088` to view the console. Images, odometry, and telemetry appear when their topics are available.

## Build and source synchronization

```bash
./scripts/build.bash
ROS_DOMAIN_ID=199 ROS_LOCALHOST_ONLY=1 ./scripts/test.bash
```

Rebuild and restart nodes after source or configuration changes. See [Contributing](CONTRIBUTING.md) for test setup and additional checks.

To copy source to a robot over SSH:

```bash
LIGHTNAV_DEPLOY_HOST='<user>@<robot-host>' \
LIGHTNAV_DEPLOY_ROOT='lightvln-scout-odin' \
  ./scripts/deploy_robot.bash
```

The script synchronizes source, excluding `.local/`, backups, and build outputs. Relative destinations are under the remote user's home. After syncing, run `./scripts/bootstrap.bash --rosdep` in the target directory on the robot. See `./scripts/deploy_robot.bash --help` for authentication options.

## Configuration and references

Use `src/integration/lightvln_scout/config/standard_stack.yaml` for robot settings. The launch files automatically load the internal defaults for image processing, interfaces, and MPC.

- [Hardware configuration](docs/hardware.md): CAN, Odin, topics, mounting TF, and motion validation.
- [Web and ROS interfaces](docs/web-adapter.md): image processing, control ownership, emergency stop, telemetry, topics, and services.
- [Contributing](CONTRIBUTING.md): development, tests, and upstream updates.
- [Licensing and third-party code](LICENSES.md): Apache-2.0 and component attribution.

Maintainer: [KevinLADLee](mailto:kevinladlee@gmail.com). Report vulnerabilities via [SECURITY.md](SECURITY.md).

The Web service has no user authentication or TLS. Use a trusted robot network or a configured gateway. Keep machine-specific settings in `.local/` or outside the repository.

## Upstream code

`src/lightnav/` contains LightNav-derived robot components, `src/integration/lightvln_scout/` owns Scout/Odin adaptation, and `src/drivers/` contains vendored drivers.

| Component | Upstream revision | Notes |
| --- | --- | --- |
| [LightNav-0](https://github.com/lightorigins/LightNav-0) | [`a645828`](https://github.com/lightorigins/LightNav-0/commit/a645828d81a8439651172197ca80a75dc1377977) | Modified robot packages; local patches in [UPSTREAM_VERSION](src/lightnav/UPSTREAM_VERSION) |
| [Manifold Odin ROS driver](https://github.com/manifoldsdk/odin_ros_driver) | [`a592cf2`](https://github.com/manifoldsdk/odin_ros_driver/commit/a592cf2cc08bc8bfb0dceae44ef31f3a6bd77822) | Includes project configuration and runtime-path changes |
| [Scout ROS 2](https://github.com/Hive-Matrix-AI/scout_ros2) | [`165083d`](https://github.com/Hive-Matrix-AI/scout_ros2/commit/165083d93942955870a96bd1b984a7b9f6f4fcdd) | Snapshot of the upstream `humble` branch |
| [AgileX UGV SDK](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk) | [`c3fa0c9`](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk/commit/c3fa0c92144dda542c45b12b7bf3c0ba8e635159) | Under `src/drivers/scout_ros2/third_party/` |
