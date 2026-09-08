// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <array>
#include <chrono>
#include <optional>

#include "agilex_ugv_sdk/core/feedback.hpp"

namespace agilex::ugv {

struct StateSnapshot {
  using TimePoint = std::chrono::steady_clock::time_point;

  std::optional<SystemState> system;
  std::optional<MotionState> motion;
  std::optional<LightState> lights;
  std::optional<RemoteControlState> remote_control;
  std::array<std::optional<ActuatorHighSpeedState>, 4> actuators_high_speed{};
  std::array<std::optional<ActuatorLowSpeedState>, 4> actuators_low_speed{};
  std::optional<OdometryState> odometry;
  std::optional<VersionInfo> version;
  std::optional<TimePoint> updated_at;
};

}  // namespace agilex::ugv
