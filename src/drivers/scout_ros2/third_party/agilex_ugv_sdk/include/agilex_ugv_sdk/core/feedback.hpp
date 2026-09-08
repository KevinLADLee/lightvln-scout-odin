// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <cstdint>
#include <memory>
#include <variant>

#include "agilex_ugv_sdk/core/robot_types.hpp"

namespace agilex::ugv {

struct SystemState {
  VehicleState vehicle_state{VehicleState::normal};
  ControlMode control_mode{ControlMode::standby};
  double battery_voltage_v{0.0};
  std::uint16_t error_flags{0};
  std::uint8_t count{0};
};

struct MotionState {
  double linear_velocity_mps{0.0};
  double angular_velocity_radps{0.0};
  double lateral_velocity_mps{0.0};
};

struct LightState {
  bool enabled{false};
  LightMode front_mode{LightMode::off};
  std::uint8_t front_value{0};
  LightMode rear_mode{LightMode::off};
  std::uint8_t rear_value{0};
  std::uint8_t count{0};
};

struct RemoteControlState {
  std::uint8_t swa{0};
  std::uint8_t swb{0};
  std::uint8_t swc{0};
  std::uint8_t swd{0};
  std::int8_t right_horizontal{0};
  std::int8_t right_vertical{0};
  std::int8_t left_vertical{0};
  std::int8_t left_horizontal{0};
  std::int8_t knob{0};
  std::uint8_t count{0};
};

struct ActuatorHighSpeedState {
  std::uint8_t index{0};
  std::int16_t speed_rpm{0};
  double current_a{0.0};
};

struct ActuatorLowSpeedState {
  std::uint8_t index{0};
  double driver_voltage_v{0.0};
  std::int16_t driver_temperature_c{0};
  std::int8_t motor_temperature_c{0};
  std::uint8_t status_flags{0};
};

struct OdometryState {
  std::int32_t left_distance_mm{0};
  std::int32_t right_distance_mm{0};
};

struct VersionInfo {
  std::uint8_t controller_hardware_major{0};
  std::uint8_t controller_hardware_minor{0};
  std::uint8_t driver_hardware_major{0};
  std::uint8_t driver_hardware_minor{0};
  std::uint8_t controller_software_major{0};
  std::uint8_t controller_software_minor{0};
  std::uint8_t driver_software_major{0};
  std::uint8_t driver_software_minor{0};
};

class ModelFeedback {
 public:
  virtual ~ModelFeedback() = default;
};

using ModelFeedbackPtr = std::shared_ptr<const ModelFeedback>;
using Feedback = std::variant<SystemState, MotionState, LightState,
                              RemoteControlState, ActuatorHighSpeedState,
                              ActuatorLowSpeedState, OdometryState, VersionInfo,
                              ModelFeedbackPtr>;

}  // namespace agilex::ugv
