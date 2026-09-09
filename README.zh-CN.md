# LightNav-0 + Scout Mini + Odin1

[![CI: GitHub Actions](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/KevinLADLee/lightvln-scout-odin/actions/workflows/ci.yml)
[![ROS 2 Humble](https://img.shields.io/badge/ROS_2-Humble-22314E?logo=ros&logoColor=white)](https://docs.ros.org/en/humble/)
[![Ubuntu 22.04](https://img.shields.io/badge/Ubuntu-22.04-E95420?logo=ubuntu&logoColor=white)](https://releases.ubuntu.com/22.04/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue)](LICENSE)

[English](README.md) | 简体中文

将 **LightNav-0 部署到搭载 Odin1 的 Scout Mini**：GPU 服务器负责模型推理，机器人端运行 ROS 2 感知、MPC 路径跟踪和底盘控制，通过浏览器完成操作与状态查看。

[开始部署](#1-部署-gpu-服务端) · [硬件配置](docs/hardware.md) · [Web 与 ROS 接口](docs/web-adapter.md) · [贡献指南](CONTRIBUTING.md)

## 本项目提供什么

- **Odin1 感知接入**：提供相机图像和里程计，模型输入与网页预览使用一致的裁剪、缩放流程。
- **MPC 路径跟踪**：按图像采集时刻匹配里程计，并应用实测的 `imu` → `base_link` 安装偏移。
- **Scout 控制与网页操作**：支持任务启停、手动控制、轨迹显示、调参和遥测，统一处理控制权、指令超时、限速与软件急停。默认关闭物理运动输出。

项目基于 [LightNav-0](https://github.com/lightorigins/LightNav-0)，机器人专属适配位于 `src/integration/lightvln_scout/`。硬件资料：[Scout Mini](https://global.agilex.ai/products/scout-mini) · [Odin1](https://manifoldtechltd.github.io/wiki/odin_series/odin1/)。

## 部署结构

| 设备 | 运行内容 | 连接入口 |
| --- | --- | --- |
| GPU 服务器 | 独立仓库中的 LightNav-0 模型与推理服务 | `ws://<gpu-host>:8050` |
| 机器人计算机 | 本仓库的 ROS 2 工作空间，包含 Odin 和 Scout 驱动 | 连接 GPU 服务端 |
| 操作电脑 | 浏览器控制台 | `http://<robot-host>:8088` |

![Odin1 感知、LightNav-0 推理、MPC、Scout Mini 控制与浏览器之间的 ROS 2 数据流。](docs/assets/ros-topology.png)

## 1. 部署 GPU 服务端

需要 **CUDA GPU、Python 3.11、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和模型权重**。在 GPU 主机上使用独立的 LightNav-0 源码目录准备环境。

### 首次安装

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

CUDA 检查应输出 `True`。下载完整权重目录，包括 `eval_config.json` 与 `action_tokenizer/`；需要认证时先登录 Hugging Face。不同 GPU 的安装细节见 [上游安装指南](https://github.com/lightorigins/LightNav-0/tree/a645828d81a8439651172197ca80a75dc1377977#installation)。

### 启动推理服务

在 **GPU 服务器的 LightNav-0 仓库根目录**执行：

```bash
uv run --no-sync lightnav-serve \
  --task tracking \
  --model_path "$PWD/checkpoints/LightNav-0" \
  --backend vllm_local \
  --gpu_memory_utilization 0.85 \
  --host 0.0.0.0 \
  --port 8050
```

等待日志出现 `[lightnav-ws] READY`，机器人端将连接 `ws://<gpu-host>:8050`。

| 使用场景 | 服务端 `--task` | 网页控制模式 |
| --- | --- | --- |
| 目标跟随 | `tracking` | `track`：持续跟踪路径 |
| 指令导航 | `vln` | `objnav`：模型返回 `stop` 时结束任务 |

网页模式不会改变服务端任务。切换任务时，使用对应的 `--task` 重启服务端，或连接另一服务实例。

## 2. 准备机器人端

需要 **Ubuntu 22.04 + ROS 2 Humble**、对应的系统 Python、C/C++ 构建工具、CMake、`colcon`、已初始化的 `rosdep` 和 `uv`。ROS 安装步骤见 [ROS 2 Humble 文档](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)。

在**机器人计算机**上执行：

```bash
git clone https://github.com/KevinLADLee/lightvln-scout-odin.git
cd lightvln-scout-odin
./scripts/bootstrap.bash --rosdep
source scripts/env.bash
```

Bootstrap 安装依赖，并使用兼容 ROS 的 `.venv` 构建工作空间；此环境与 GPU 服务端的 Python 环境分开。每次打开新终端，Bash 执行 `source scripts/env.bash`，Zsh 执行 `source scripts/env.zsh`。系统依赖已安装时可省略 `--rosdep`。

按 [硬件配置](docs/hardware.md) 完成 Scout SocketCAN、Odin USB 权限与传感器安装测量。

## 3. 启动机器人并连接服务端

编辑 [standard_stack.yaml](src/integration/lightvln_scout/config/standard_stack.yaml)。只需关注以下机器人配置，图像处理、接口和 MPC 会自动加载默认值。

| 分组（`ros__parameters`） | 为当前机器人设置 |
| --- | --- |
| `vln_client` | `server_url`：`ws://<gpu-host>:8050` |
| `robot_launch` | `scout_port` 及六个实测的 `imu_to_base_*` 安装偏移 |
| `scout_adapter` | 首次运行保持 `hardware_output_enabled: false` |

两个驱动均未运行时，启动完整组合，包含 Odin、Scout 和 RViz：

```bash
ros2 launch lightvln_scout scout_odin.launch.py
```

驱动已单独启动，或无硬件时仅预览控制台：

```bash
ros2 launch lightvln_scout controller_only.launch.py
```

无显示器部署及独立机器 YAML 的用法见 [硬件配置](docs/hardware.md#parameter-presets)。

浏览器打开 **`http://<robot-host>:8088`**；在机器人本机访问时使用 `http://localhost:8088`：

1. 检查相机、Odin 里程计、Scout 诊断及推理地址；地址也可在网页中修改。
2. 按上表选择网页控制模式，输入指令并启动任务。
3. 保持物理输出关闭，检查推理延迟、返回轨迹与 MPC 跟踪效果。
4. 按 [运动验证步骤](docs/hardware.md#enable-motion-after-validation) 开启 `hardware_output_enabled` 并验证底盘控制。

对应话题接入后即可显示图像和遥测。Web 服务不含用户认证或 TLS，请在可信机器人网络中使用。

## 开发与参考

修改源码或配置后，重新构建并重启：

```bash
./scripts/build.bash
./scripts/test.bash
```

- [硬件配置](docs/hardware.md)：机器预设、设备、安装 TF 与故障排查。
- [Web 与 ROS 接口](docs/web-adapter.md)：图像处理、控制行为、话题与服务。
- [贡献指南](CONTRIBUTING.md)：开发检查、源码同步与上游更新。
- [许可与第三方代码](LICENSES.md)：Apache-2.0 许可与组件来源。

以上技术参考为英文。维护者：[KevinLADLee](mailto:kevinladlee@gmail.com)。安全问题请通过 [SECURITY.md](SECURITY.md) 私下反馈。

## 上游代码

`src/lightnav/` 保存 LightNav 机器人端组件，`src/integration/lightvln_scout/` 负责 Scout/Odin 适配，`src/drivers/` 保存驱动快照。

| 组件 | 上游 revision | 说明 |
| --- | --- | --- |
| [LightNav-0](https://github.com/lightorigins/LightNav-0) | [`a645828`](https://github.com/lightorigins/LightNav-0/commit/a645828d81a8439651172197ca80a75dc1377977) | 机器人端组件快照；本地修改见 [UPSTREAM_VERSION](src/lightnav/UPSTREAM_VERSION) |
| [Manifold Odin ROS driver](https://github.com/manifoldsdk/odin_ros_driver) | [`a592cf2`](https://github.com/manifoldsdk/odin_ros_driver/commit/a592cf2cc08bc8bfb0dceae44ef31f3a6bd77822) | 包含本项目配置和运行路径修改 |
| [Scout ROS 2](https://github.com/Hive-Matrix-AI/scout_ros2) | [`165083d`](https://github.com/Hive-Matrix-AI/scout_ros2/commit/165083d93942955870a96bd1b984a7b9f6f4fcdd) | 上游 `humble` 分支快照 |
| [AgileX UGV SDK](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk) | [`c3fa0c9`](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk/commit/c3fa0c92144dda542c45b12b7bf3c0ba8e635159) | 位于 `src/drivers/scout_ros2/third_party/` |
