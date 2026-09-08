// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <cstdint>
#include <memory>
#include <variant>

#include "agilex_ugv_sdk/core/robot_types.hpp"

namespace agilex::ugv {

struct MotionCommand {
  double linear_velocity_mps{0.0};
  double angular_velocity_radps{0.0};
  double lateral_velocity_mps{0.0};
};

struct LightCommand {
  bool enabled{true};
  LightMode front_mode{LightMode::off};
  std::uint8_t front_value{0};
  LightMode rear_mode{LightMode::off};
  std::uint8_t rear_value{0};
};

struct ControlModeCommand {
  ControlMode mode{ControlMode::standby};
};

struct ClearErrorCommand {
  // 0 clears all errors; other values identify a motor.
  std::uint8_t motor{0};
};

struct VersionRequest {};

class ModelCommand {
 public:
  virtual ~ModelCommand() = default;
};

using ModelCommandPtr = std::shared_ptr<const ModelCommand>;
using Command = std::variant<MotionCommand, LightCommand, ControlModeCommand,
                             ClearErrorCommand, VersionRequest, ModelCommandPtr>;

}  // namespace agilex::ugv
