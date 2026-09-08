# Changelog for agilex_ugv_sdk

## 1.1.0 (2026-09-08)

- Organized public headers into core, protocol, transport, and model components.
- Added component-specific command, feedback, state, and capability headers.
  Existing 1.0 include paths remain supported.
- Grouped model sources, examples, tests, and protocol references by family.
- SCOUT ROS 2 diagnostics are provided by `scout_base` in `scout_ros2`.
- The SDK uses standard CMake exports in every environment and has no ROS build
  dependencies.
- Removed legacy sources, examples, and protocol-detection utilities that were
  excluded from the 1.0 build and installation.
- Added standalone installation and API usage instructions.
- Included the license and package documentation in installed distributions.

## 1.0.0 (2026-09-05)

- Rebuilt the SDK around C++17 value types, RAII and injectable transports.
- Added the strongly typed SCOUT MINI / SCOUT MINI OMNI CAN profile.
- Added standalone CMake and ROS 2 Humble package exports.
- Added protocol, transport and robot-state regression tests.
- Added a SCOUT MINI CAN protocol reference.
- Excluded the legacy SDK implementation from the modern build and install surface.

The entries below describe the pre-1.0 upstream implementation and are retained
for historical context.

## 0.1.5 (2020-06-17)
-------------------
* Merged multiple small libraries into one "wrp_sdk"
* Changed to "plain" project structure
* Contributors: Ruixiang Du

## 0.1.4 (2020-04-01)
-------------------
* Added initial support of Hunter
* Contributors: Ruixiang Du

## 0.1.3 (2019-09-15)
------------------
* Unified implementation of UART/CAN for firmware and SDK
* Improvements of code organization
* Contributors: Ruixiang Du

## 0.1.2 (2019-08-02)
------------------
* Added full UART support
* Contributors: Ruixiang Du

## 0.1.1 (2019-06-14)
------------------
* Deprecated initial serial interface support
* Added full CAN support
* Improved multi-threading implementation
* Contributors: Ruixiang Du
  
## 0.1.0 (2019-05-07)
------------------

* Added basic serial communication support 
* Provided C++ interface, ROS/LCM demo
* Contributors: Ruixiang Du
