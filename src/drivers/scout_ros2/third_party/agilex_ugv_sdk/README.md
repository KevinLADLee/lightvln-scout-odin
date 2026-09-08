# AgileX UGV SDK

[![C++17](https://img.shields.io/badge/C%2B%2B-17-00599C?logo=cplusplus&logoColor=white)](#quick-start)
[![CMake](https://img.shields.io/badge/CMake-3.16%2B-064F8C?logo=cmake&logoColor=white)](#quick-start)
[![Linux](https://img.shields.io/badge/platform-Linux-FCC624?logo=linux&logoColor=black)](#quick-start)
[![SocketCAN](https://img.shields.io/badge/transport-SocketCAN-3C8D6E)](#connect-a-robot)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**A shared C++ foundation for new AgileX mobile robots.**

`agilex_ugv_sdk` brings CAN communication, typed commands, and robot feedback
into one extensible library. Use a model API to connect to your robot, or build
on the shared interfaces to support another AgileX model.

[Quick start](#quick-start) · [Supported models](#supported-models) ·
[API](#api-overview) · [CAN reference](docs/reference/models/scout/scout_mini_can.md) ·
[Changelog](CHANGELOG.md)

## Highlights

- **One core, multiple models.** Shared robot and transport interfaces with
  model-specific protocol codecs and capability descriptions.
- **Typed commands and feedback.** Explicit units, model limits, and
  `std::error_code` results for connection and command failures.
- **State you can use.** Thread-safe state snapshots and feedback callbacks
  for motion, battery, actuators, lights, remote control, and version data.
- **Easy to integrate and test.** C++17, an exported CMake target, Linux
  SocketCAN, and injectable transports for tests without hardware.

## Supported models

| Family | Model | Status |
| --- | --- | --- |
| SCOUT | SCOUT MINI | Supported |
| SCOUT | SCOUT MINI OMNI | Supported |

Current model support covers SCOUT MINI and SCOUT MINI OMNI. Shared robot,
transport, and protocol interfaces provide the foundation for adding AgileX models.

## Quick start

Requires **Linux**, a **C++17 compiler**, and **CMake 3.16+**.

```bash
git clone https://github.com/Hive-Matrix-AI/agilex_ugv_sdk.git
cd agilex_ugv_sdk
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure
cmake --install build --prefix "$HOME/.local"
```

Link the installed SDK from your CMake project:

```cmake
find_package(agilex_ugv_sdk 1 REQUIRED)
target_link_libraries(my_target PRIVATE agilex_ugv_sdk::agilex_ugv_sdk)
```

The public namespace is `agilex::ugv`. If CMake cannot locate the package,
configure your project with `-DCMAKE_PREFIX_PATH="$HOME/.local"`.

<details>
<summary>Build options</summary>

| Option | Default | Purpose |
| --- | --- | --- |
| `BUILD_TESTING` | `ON` | Protocol and robot/transport tests without hardware |
| `BUILD_EXAMPLES` | `OFF` | Standalone state-monitor example |

</details>

## Connect a robot

For SCOUT MINI and SCOUT MINI OMNI, configure SocketCAN at **500 kbit/s**.
Replace `can0` with your adapter's interface:

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 500000 restart-ms 100
sudo ip link set can0 up
ip -details -statistics link show can0
./build/scout_mini_state can0
```

The [state-monitor example](examples/scout/scout_mini_state.cpp) prints battery
voltage and error flags as feedback arrives. It does not enable motion.
Stop it with `Ctrl+C`.

## API overview

| Interface | Responsibility |
| --- | --- |
| `CanFrame` / `CanTransport` | Frame values and CAN I/O; SocketCAN is the provided backend |
| `ProtocolCodec` / `ModelCapabilities` | Model-specific encoding, decoding, and supported features |
| `Robot` | Compose a codec and transport; expose commands, state, and callbacks |
| `ScoutMini` | Ready-to-use API for the currently supported SCOUT models |

Common commands and feedback use shared types. `ModelCommand` and
`ModelFeedback` provide extension points for model-specific data.

<details>
<summary>Package layout</summary>

```text
include/agilex_ugv_sdk/
  core/                   Commands, feedback, state, and robot interface
  protocol/               Codec interface and encode/decode results
  transport/              CAN frames, transport interface, and backends
  models/scout/           SCOUT MINI API and codec
src/
  core/                   Shared robot implementation
  transport/              Transport backends
  models/scout/           SCOUT MINI implementation
tests/
  core/                   Tests with model-independent codecs
  models/scout/           SCOUT API and protocol tests
  support/                Shared test transports and assertions
examples/scout/           Standalone SCOUT examples
docs/reference/models/    Protocol references grouped by model family
```

Each model family groups its API and codec under `models/<family>/`, with
corresponding sources, tests, examples, and protocol references. Family-local
CMake files register their sources with the shared library target.

Headers use the component paths above. The original 1.0 header paths remain
available as forwarding includes for existing applications.

</details>

<details>
<summary>SCOUT MINI methods and command behavior</summary>

Include `agilex_ugv_sdk/models/scout/scout_mini.hpp` and construct
`agilex::ugv::ScoutMini`.
The default variant is `ScoutMiniVariant::skid_steer`; pass
`ScoutMiniVariant::omni` for SCOUT MINI OMNI.

| Method | Purpose |
| --- | --- |
| `connect("can0")` / `disconnect()` | Open or close the transport |
| `state()` | Copy the latest state; fields are optional until feedback arrives |
| `set_feedback_handler(handler)` | Receive decoded feedback on the transport thread |
| `request_version()` | Request controller and driver versions |
| `set_control_mode(ControlMode::can)` | Enable CAN commanded mode |
| `set_motion(command)` / `stop()` | Send one velocity or zero-speed command |
| `set_lights(command)` | Set front and rear light modes |
| `clear_error(motor)` | Clear all errors (`0`) or motor errors (`1`–`4`) |

Check the `std::error_code` returned by connection and command methods.
Commands outside model limits are rejected; feedback with invalid CAN IDs
or DLC is not added to state snapshots.

For SCOUT MINI motion, select CAN control mode and send commands every 20 ms.
The SDK does not repeat commands in the background. `stop()` sends one
zero-speed frame; disconnecting does not send a stop command. Keep the physical
emergency stop within reach during motion tests.

Feedback callbacks must return promptly and must not disconnect or destroy
the robot from the receive thread. See the
[CAN reference](docs/reference/models/scout/scout_mini_can.md) for units, limits, frame
formats, and controller timeout behavior.

</details>

## Integrations

SCOUT ROS 2 drivers and diagnostics are maintained in
[scout_ros2](https://github.com/Hive-Matrix-AI/scout_ros2).

## License

Licensed under [Apache-2.0](LICENSE). Existing copyright and attribution notices
are retained in the source.

## Contributing

Bug reports, tests, and support for additional AgileX models are welcome.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution and test workflow.
