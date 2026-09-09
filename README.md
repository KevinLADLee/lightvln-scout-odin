# LightNav-0 + Scout Mini + Odin1

[![CI: GitHub Actions](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/KevinLADLee/lightvln-scout-odin/actions/workflows/ci.yml)
[![ROS 2 Humble](https://img.shields.io/badge/ROS_2-Humble-22314E?logo=ros&logoColor=white)](https://docs.ros.org/en/humble/)
[![Ubuntu 22.04](https://img.shields.io/badge/Ubuntu-22.04-E95420?logo=ubuntu&logoColor=white)](https://releases.ubuntu.com/22.04/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue)](LICENSE)

English | [简体中文](README.zh-CN.md)

Deploy **LightNav-0 on Scout Mini with Odin1**. The GPU server runs model inference; the robot runs ROS 2 perception, MPC path tracking, and Scout control. Operate and monitor the robot from a browser.

[Deployment](#1-deploy-the-gpu-server) · [Hardware setup](docs/hardware.md) · [Web & ROS interfaces](docs/web-adapter.md) · [Contributing](CONTRIBUTING.md)

## What this integration provides

- **Odin1 perception:** camera images and odometry, with a shared crop and resize pipeline for model input and browser preview.
- **MPC tracking:** capture-time odometry matching and measured `imu` → `base_link` mounting offsets.
- **Scout control and console:** task start/stop, manual control, trajectories, tuning, and telemetry, with control ownership, command timeouts, speed limits, and software emergency stop. Physical motion output is disabled by default.

The integration builds on [LightNav-0](https://github.com/lightorigins/LightNav-0), with robot-specific adaptation in `src/integration/lightvln_scout/`. Hardware references: [Scout Mini](https://global.agilex.ai/products/scout-mini) · [Odin1](https://manifoldtechltd.github.io/wiki/odin_series/odin1/).

## Deployment architecture

| Machine | Runs | Connection |
| --- | --- | --- |
| GPU server | LightNav-0 model and inference service, in a separate checkout | `ws://<gpu-host>:8050` |
| Robot computer | This ROS 2 workspace, including Odin and Scout drivers | Connects to the GPU server |
| Operator computer | Browser console | `http://<robot-host>:8088` |

![ROS 2 data flow between Odin1 perception, LightNav-0 inference, MPC, Scout Mini control, and the browser console.](docs/assets/ros-topology.png)

## 1. Deploy the GPU server

Requires a **CUDA GPU, Python 3.11, [uv](https://docs.astral.sh/uv/getting-started/installation/), and model weights**. Prepare these in a separate LightNav-0 checkout on the GPU host.

### First-time setup

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

The CUDA check should print `True`. Download the complete checkpoint, including `eval_config.json` and `action_tokenizer/`; sign in to Hugging Face if required. For GPU-specific installation details, see the [upstream installation guide](https://github.com/lightorigins/LightNav-0/tree/a645828d81a8439651172197ca80a75dc1377977#installation).

### Start inference

From the **LightNav-0 repository root on the GPU server**:

```bash
uv run --no-sync lightnav-serve \
  --task tracking \
  --model_path "$PWD/checkpoints/LightNav-0" \
  --backend vllm_local \
  --gpu_memory_utilization 0.85 \
  --host 0.0.0.0 \
  --port 8050
```

Wait for `[lightnav-ws] READY`. The robot will connect to `ws://<gpu-host>:8050`.

| Use case | Server `--task` | Console mode |
| --- | --- | --- |
| Target following | `tracking` | `track`: continuously follow the path |
| Instruction navigation | `vln` | `objnav`: finish when the model returns `stop` |

Changing the console mode does not change the server task. Restart the server with the required `--task`, or connect to another instance.

## 2. Prepare the robot computer

Requires **Ubuntu 22.04 + ROS 2 Humble**, the matching system Python, C/C++ build tools, CMake, `colcon`, initialized `rosdep`, and `uv`. Start with the [ROS 2 Humble installation guide](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html).

On the **robot computer**:

```bash
git clone https://github.com/KevinLADLee/lightvln-scout-odin.git
cd lightvln-scout-odin
./scripts/bootstrap.bash --rosdep
source scripts/env.bash
```

Bootstrap installs dependencies and builds the workspace in a ROS-compatible `.venv`. Keep it separate from the GPU server's Python environment. In each new shell, source `scripts/env.bash` (Bash) or `scripts/env.zsh` (Zsh). If system dependencies are already installed, omit `--rosdep`.

Complete [hardware setup](docs/hardware.md): Scout SocketCAN, Odin USB permissions, and sensor mounting measurements.

## 3. Launch the robot and connect the server

Edit [standard_stack.yaml](src/integration/lightvln_scout/config/standard_stack.yaml). Only these robot settings need attention; image processing, interfaces, and MPC load their defaults automatically.

| Section (`ros__parameters`) | Set once for this robot |
| --- | --- |
| `vln_client` | `server_url`: `ws://<gpu-host>:8050` |
| `robot_launch` | `scout_port` and six measured `imu_to_base_*` mounting offsets |
| `scout_adapter` | Keep `hardware_output_enabled: false` for the first run |

Start the full stack, including Odin, Scout, and RViz, when both drivers are stopped:

```bash
ros2 launch lightvln_scout scout_odin.launch.py
```

When drivers are already running, or to preview the console without hardware:

```bash
ros2 launch lightvln_scout controller_only.launch.py
```

For headless deployment or a separate machine YAML, see [hardware configuration](docs/hardware.md#parameter-presets).

Open **`http://<robot-host>:8088`** in a browser (`http://localhost:8088` on the robot):

1. Check the camera, Odin odometry, Scout diagnostics, and inference URL. The URL can also be edited in the console.
2. Select the console mode from the table above, enter an instruction, and start the task.
3. Check inference latency, returned trajectories, and MPC behavior while physical output remains locked.
4. Follow [motion validation](docs/hardware.md#enable-motion-after-validation) before enabling `hardware_output_enabled` and driving the base.

Images and telemetry appear once their publishers are available. Use the console on a trusted robot network; its Web service has no authentication or TLS.

## Development and references

After source or configuration changes, rebuild and restart the stack:

```bash
./scripts/build.bash
./scripts/test.bash
```

- [Hardware configuration](docs/hardware.md): machine presets, devices, mounting TF, and troubleshooting.
- [Web and ROS interfaces](docs/web-adapter.md): image processing, control behavior, topics, and services.
- [Contributing](CONTRIBUTING.md): development checks, source synchronization, and upstream updates.
- [Licensing and third-party code](LICENSES.md): Apache-2.0 and component attribution.

Maintainer: [KevinLADLee](mailto:kevinladlee@gmail.com). Report vulnerabilities privately via [SECURITY.md](SECURITY.md).

## Upstream code

`src/lightnav/` contains LightNav-derived robot components, `src/integration/lightvln_scout/` owns Scout/Odin adaptation, and `src/drivers/` contains vendored drivers.

| Component | Upstream revision | Notes |
| --- | --- | --- |
| [LightNav-0](https://github.com/lightorigins/LightNav-0) | [`a645828`](https://github.com/lightorigins/LightNav-0/commit/a645828d81a8439651172197ca80a75dc1377977) | Modified robot packages; local patches in [UPSTREAM_VERSION](src/lightnav/UPSTREAM_VERSION) |
| [Manifold Odin ROS driver](https://github.com/manifoldsdk/odin_ros_driver) | [`a592cf2`](https://github.com/manifoldsdk/odin_ros_driver/commit/a592cf2cc08bc8bfb0dceae44ef31f3a6bd77822) | Includes project configuration and runtime-path changes |
| [Scout ROS 2](https://github.com/Hive-Matrix-AI/scout_ros2) | [`165083d`](https://github.com/Hive-Matrix-AI/scout_ros2/commit/165083d93942955870a96bd1b984a7b9f6f4fcdd) | Snapshot of the upstream `humble` branch |
| [AgileX UGV SDK](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk) | [`c3fa0c9`](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk/commit/c3fa0c92144dda542c45b12b7bf3c0ba8e635159) | Under `src/drivers/scout_ros2/third_party/` |
