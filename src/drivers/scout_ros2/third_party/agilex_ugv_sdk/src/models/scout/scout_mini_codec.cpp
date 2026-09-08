// SPDX-License-Identifier: Apache-2.0

#include "agilex_ugv_sdk/models/scout/scout_mini_codec.hpp"

#include <cmath>
#include <cstdint>
#include <limits>
#include <type_traits>
#include <utility>

namespace agilex::ugv {
namespace {

constexpr std::uint32_t kMotionCommandId = 0x111;
constexpr std::uint32_t kLightCommandId = 0x121;
constexpr std::uint32_t kSystemStateId = 0x211;
constexpr std::uint32_t kMotionStateId = 0x221;
constexpr std::uint32_t kLightStateId = 0x231;
constexpr std::uint32_t kRemoteControlStateId = 0x241;
constexpr std::uint32_t kActuatorHighSpeedFirstId = 0x251;
constexpr std::uint32_t kActuatorHighSpeedLastId = 0x254;
constexpr std::uint32_t kActuatorLowSpeedFirstId = 0x261;
constexpr std::uint32_t kActuatorLowSpeedLastId = 0x264;
constexpr std::uint32_t kOdometryStateId = 0x311;
constexpr std::uint32_t kVersionRequestId = 0x411;
constexpr std::uint32_t kVersionFeedbackId = 0x41A;
constexpr std::uint32_t kControlModeId = 0x421;
constexpr std::uint32_t kClearErrorId = 0x441;

template <class... Ts>
struct Overloaded : Ts... {
  using Ts::operator()...;
};
template <class... Ts>
Overloaded(Ts...) -> Overloaded<Ts...>;

void write_u16_be(std::uint16_t value, std::uint8_t* destination) noexcept {
  destination[0] = static_cast<std::uint8_t>(value >> 8U);
  destination[1] = static_cast<std::uint8_t>(value & 0xFFU);
}

void write_i16_be(std::int16_t value, std::uint8_t* destination) noexcept {
  write_u16_be(static_cast<std::uint16_t>(value), destination);
}

std::uint16_t read_u16_be(const std::uint8_t* source) noexcept {
  return static_cast<std::uint16_t>(
      (static_cast<std::uint16_t>(source[0]) << 8U) |
      static_cast<std::uint16_t>(source[1]));
}

std::int16_t read_i16_be(const std::uint8_t* source) noexcept {
  const auto raw = read_u16_be(source);
  if (raw <= static_cast<std::uint16_t>(std::numeric_limits<std::int16_t>::max())) {
    return static_cast<std::int16_t>(raw);
  }
  return static_cast<std::int16_t>(static_cast<std::int32_t>(raw) - 0x10000);
}

std::int32_t read_i32_be(const std::uint8_t* source) noexcept {
  const auto raw = (static_cast<std::uint32_t>(source[0]) << 24U) |
                   (static_cast<std::uint32_t>(source[1]) << 16U) |
                   (static_cast<std::uint32_t>(source[2]) << 8U) |
                   static_cast<std::uint32_t>(source[3]);
  if (raw <= static_cast<std::uint32_t>(std::numeric_limits<std::int32_t>::max())) {
    return static_cast<std::int32_t>(raw);
  }
  return static_cast<std::int32_t>(static_cast<std::int64_t>(raw) - 0x100000000LL);
}

std::int8_t read_i8(std::uint8_t raw) noexcept {
  if (raw <= static_cast<std::uint8_t>(std::numeric_limits<std::int8_t>::max())) {
    return static_cast<std::int8_t>(raw);
  }
  return static_cast<std::int8_t>(static_cast<std::int16_t>(raw) - 0x100);
}

bool scaled_i16(double value, double scale, std::int16_t minimum,
                std::int16_t maximum, std::int16_t& output) noexcept {
  if (!std::isfinite(value)) {
    return false;
  }
  const auto scaled = std::llround(value / scale);
  if (scaled < minimum || scaled > maximum) {
    return false;
  }
  output = static_cast<std::int16_t>(scaled);
  return true;
}

bool valid_light_mode(LightMode mode) noexcept {
  return static_cast<std::uint8_t>(mode) <=
         static_cast<std::uint8_t>(LightMode::custom);
}

DecodeResult invalid_dlc() {
  return {DecodeStatus::invalid_dlc, std::nullopt};
}

}  // namespace

ModelCapabilities ScoutMiniCodec::capabilities() const noexcept {
  return {variant_ == ScoutMiniVariant::omni ? "SCOUT MINI OMNI" : "SCOUT MINI",
          4, variant_ == ScoutMiniVariant::omni, true};
}

EncodeResult ScoutMiniCodec::encode(const Command& command) {
  return std::visit(
      Overloaded{
          [this](const MotionCommand& value) -> EncodeResult {
            std::int16_t linear{};
            std::int16_t angular{};
            std::int16_t lateral{};
            if (!scaled_i16(value.linear_velocity_mps, 0.001, -3000, 3000,
                            linear) ||
                !scaled_i16(value.angular_velocity_radps, 0.001, -2523, 2523,
                            angular) ||
                !scaled_i16(value.lateral_velocity_mps, 0.001, -2000, 2000,
                            lateral)) {
              return {{}, Error::value_out_of_range};
            }
            if (variant_ == ScoutMiniVariant::skid_steer && lateral != 0) {
              return {{}, Error::unsupported_command};
            }

            CanFrame frame{kMotionCommandId, 8, {}};
            write_i16_be(linear, &frame.data[0]);
            write_i16_be(angular, &frame.data[2]);
            write_i16_be(lateral, &frame.data[4]);
            return {frame, {}};
          },
          [this](const LightCommand& value) -> EncodeResult {
            if (!valid_light_mode(value.front_mode) ||
                !valid_light_mode(value.rear_mode) || value.front_value > 100U) {
              return {{}, Error::value_out_of_range};
            }
            CanFrame frame{kLightCommandId, 8, {}};
            frame.data[0] = value.enabled ? 1U : 0U;
            frame.data[1] = static_cast<std::uint8_t>(value.front_mode);
            frame.data[2] = value.front_value;
            frame.data[3] = static_cast<std::uint8_t>(value.rear_mode);
            frame.data[4] = value.rear_value;
            frame.data[7] = light_count_++;
            return {frame, {}};
          },
          [](const ControlModeCommand& value) -> EncodeResult {
            if (value.mode != ControlMode::standby && value.mode != ControlMode::can) {
              return {{}, Error::value_out_of_range};
            }
            CanFrame frame{kControlModeId, 1, {}};
            frame.data[0] = static_cast<std::uint8_t>(value.mode);
            return {frame, {}};
          },
          [](const ClearErrorCommand& value) -> EncodeResult {
            if (value.motor > 4U) {
              return {{}, Error::value_out_of_range};
            }
            CanFrame frame{kClearErrorId, 1, {}};
            frame.data[0] = value.motor;
            return {frame, {}};
          },
          [](const VersionRequest&) -> EncodeResult {
            CanFrame frame{kVersionRequestId, 1, {}};
            frame.data[0] = 0x01;
            return {frame, {}};
          },
          [](const ModelCommandPtr&) -> EncodeResult {
            return {{}, Error::unsupported_command};
          }},
      command);
}

DecodeResult ScoutMiniCodec::decode(const CanFrame& frame) const {
  if (!frame.valid()) {
    return {DecodeStatus::invalid_frame, std::nullopt};
  }

  switch (frame.id) {
    case kSystemStateId: {
      if (frame.size != 8U) return invalid_dlc();
      SystemState state;
      state.vehicle_state = static_cast<VehicleState>(frame.data[0]);
      state.control_mode = static_cast<ControlMode>(frame.data[1]);
      state.battery_voltage_v = static_cast<double>(read_u16_be(&frame.data[2])) * 0.1;
      state.error_flags = read_u16_be(&frame.data[4]);
      state.count = frame.data[7];
      return {DecodeStatus::decoded, Feedback{state}};
    }
    case kMotionStateId: {
      if (frame.size != 8U) return invalid_dlc();
      MotionState state;
      state.linear_velocity_mps = static_cast<double>(read_i16_be(&frame.data[0])) * 0.001;
      state.angular_velocity_radps = static_cast<double>(read_i16_be(&frame.data[2])) * 0.001;
      state.lateral_velocity_mps = static_cast<double>(read_i16_be(&frame.data[4])) * 0.001;
      return {DecodeStatus::decoded, Feedback{state}};
    }
    case kLightStateId: {
      if (frame.size != 8U) return invalid_dlc();
      LightState state;
      state.enabled = frame.data[0] != 0U;
      state.front_mode = static_cast<LightMode>(frame.data[1]);
      state.front_value = frame.data[2];
      state.rear_mode = static_cast<LightMode>(frame.data[3]);
      state.rear_value = frame.data[4];
      state.count = frame.data[7];
      return {DecodeStatus::decoded, Feedback{state}};
    }
    case kRemoteControlStateId: {
      if (frame.size != 8U) return invalid_dlc();
      RemoteControlState state;
      state.swa = frame.data[0] & 0x03U;
      state.swb = (frame.data[0] >> 2U) & 0x03U;
      state.swc = (frame.data[0] >> 4U) & 0x03U;
      state.swd = (frame.data[0] >> 6U) & 0x03U;
      state.right_horizontal = read_i8(frame.data[1]);
      state.right_vertical = read_i8(frame.data[2]);
      state.left_vertical = read_i8(frame.data[3]);
      state.left_horizontal = read_i8(frame.data[4]);
      state.knob = read_i8(frame.data[5]);
      state.count = frame.data[7];
      return {DecodeStatus::decoded, Feedback{state}};
    }
    case kOdometryStateId: {
      if (frame.size != 8U) return invalid_dlc();
      OdometryState state;
      state.left_distance_mm = read_i32_be(&frame.data[0]);
      state.right_distance_mm = read_i32_be(&frame.data[4]);
      return {DecodeStatus::decoded, Feedback{state}};
    }
    case kVersionFeedbackId: {
      if (frame.size != 8U) return invalid_dlc();
      VersionInfo version;
      version.controller_hardware_major = frame.data[0];
      version.controller_hardware_minor = frame.data[1];
      version.driver_hardware_major = frame.data[2];
      version.driver_hardware_minor = frame.data[3];
      version.controller_software_major = frame.data[4];
      version.controller_software_minor = frame.data[5];
      version.driver_software_major = frame.data[6];
      version.driver_software_minor = frame.data[7];
      return {DecodeStatus::decoded, Feedback{version}};
    }
    default:
      break;
  }

  if (frame.id >= kActuatorHighSpeedFirstId &&
      frame.id <= kActuatorHighSpeedLastId) {
    if (frame.size != 8U) return invalid_dlc();
    ActuatorHighSpeedState state;
    state.index = static_cast<std::uint8_t>(frame.id - kActuatorHighSpeedFirstId + 1U);
    state.speed_rpm = read_i16_be(&frame.data[0]);
    state.current_a = static_cast<double>(read_i16_be(&frame.data[2])) * 0.1;
    return {DecodeStatus::decoded, Feedback{state}};
  }

  if (frame.id >= kActuatorLowSpeedFirstId &&
      frame.id <= kActuatorLowSpeedLastId) {
    if (frame.size != 8U) return invalid_dlc();
    ActuatorLowSpeedState state;
    state.index = static_cast<std::uint8_t>(frame.id - kActuatorLowSpeedFirstId + 1U);
    state.driver_voltage_v = static_cast<double>(read_u16_be(&frame.data[0])) * 0.1;
    state.driver_temperature_c = read_i16_be(&frame.data[2]);
    state.motor_temperature_c = read_i8(frame.data[4]);
    state.status_flags = frame.data[5];
    return {DecodeStatus::decoded, Feedback{state}};
  }

  return {DecodeStatus::ignored, std::nullopt};
}

ProtocolCodecPtr make_scout_mini_codec(ScoutMiniVariant variant) {
  return std::make_unique<ScoutMiniCodec>(variant);
}

}  // namespace agilex::ugv
