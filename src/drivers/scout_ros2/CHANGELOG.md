# Changelog

Notable user-facing changes to this repository are documented here.

## Unreleased

### Added

- Ubuntu 24.04 / ROS 2 Jazzy support alongside Ubuntu 22.04 / ROS 2 Humble,
  with build, test, and installed-entry-point checks for both environments.
- An auxiliary, dependency-light `scout_base` terminal dashboard for status,
  odometry, actuator, light, RC, and guarded low-speed motion tests.
- SCOUT MINI CAN diagnostics via `ros2 run scout_base scout_mini_smoke`.

### Changed

- Documented installation, SocketCAN configuration, ROS interfaces, and hardware
  validation.
- Removed unused legacy driver sources and launch files. The supported entry
  point is `scout_mini.launch.py` for both SCOUT MINI variants.
- Corrected robot-description mesh paths and declared its runtime dependencies.
- Moved SCOUT ROS diagnostics from the SDK into `scout_base`; the SDK is now
  built as a standard CMake dependency.

## 1.0.0 - 2026-09-05

- Initial ROS 2 Humble driver release for SCOUT MINI and SCOUT MINI OMNI.
