// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <cstdint>

namespace agilex::ugv {

enum class VehicleState : std::uint8_t {
  normal = 0x00,
  emergency_stop = 0x01,
  exception = 0x02,
};

enum class ControlMode : std::uint8_t {
  standby = 0x00,
  can = 0x01,
  uart = 0x02,
  remote_control = 0x03,
};

enum class LightMode : std::uint8_t {
  off = 0x00,
  on = 0x01,
  breath = 0x02,
  custom = 0x03,
};

}  // namespace agilex::ugv
