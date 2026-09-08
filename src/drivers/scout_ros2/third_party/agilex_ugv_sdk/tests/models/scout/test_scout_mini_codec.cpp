// SPDX-License-Identifier: Apache-2.0

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <memory>
#include <string_view>
#include <utility>
#include <variant>

#include "agilex_ugv_sdk/models/scout/scout_mini_codec.hpp"
#include "support/assertions.hpp"

namespace {

using agilex::ugv::testing::expect;

bool near(double lhs, double rhs) { return std::abs(lhs - rhs) < 1e-9; }

class ForeignModelCommand final : public agilex::ugv::ModelCommand {};

template <typename T>
const T& decoded_as(const agilex::ugv::DecodeResult& result) {
  expect(static_cast<bool>(result), "frame should decode");
  expect(std::holds_alternative<T>(*result.feedback), "decoded type mismatch");
  return std::get<T>(*result.feedback);
}

void test_commands() {
  using namespace agilex::ugv;
  ScoutMiniCodec skid;

  auto result = skid.encode(MotionCommand{0.15, 0.2, 0.0});
  expect(static_cast<bool>(result), "valid motion command");
  expect(result.frame.id == 0x111 && result.frame.size == 8, "motion ID and DLC");
  expect(result.frame.data == std::array<std::uint8_t, 8>{0x00, 0x96, 0x00, 0xC8,
                                                         0x00, 0x00, 0x00, 0x00},
         "motion big-endian payload and reserved bytes");

  result = skid.encode(MotionCommand{0.0, 0.0, 0.001});
  expect(result.error == Error::unsupported_command, "skid rejects lateral motion");
  result = skid.encode(MotionCommand{3.001, 0.0, 0.0});
  expect(result.error == Error::value_out_of_range, "linear range is enforced");
  result = skid.encode(MotionCommand{std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0});
  expect(result.error == Error::value_out_of_range, "non-finite motion is rejected");

  ScoutMiniCodec omni{ScoutMiniVariant::omni};
  result = omni.encode(MotionCommand{-0.001, -0.002, -0.003});
  expect(static_cast<bool>(result), "omni lateral motion");
  expect(result.frame.data[0] == 0xFF && result.frame.data[1] == 0xFF &&
             result.frame.data[2] == 0xFF && result.frame.data[3] == 0xFE &&
             result.frame.data[4] == 0xFF && result.frame.data[5] == 0xFD,
         "negative two's-complement encoding");

  result = skid.encode(LightCommand{true, LightMode::custom, 10, LightMode::breath, 200});
  expect(static_cast<bool>(result), "valid light command");
  expect(result.frame.id == 0x121 && result.frame.size == 8, "light ID and DLC");
  expect(result.frame.data == std::array<std::uint8_t, 8>{1, 3, 10, 2, 200, 0, 0, 0},
         "light layout");
  result = skid.encode(LightCommand{});
  expect(result.frame.data[7] == 1, "light rolling count");

  result = skid.encode(ControlModeCommand{ControlMode::can});
  expect(result.frame.id == 0x421 && result.frame.size == 1 && result.frame.data[0] == 1,
         "control mode uses DLC 1");
  result = skid.encode(ControlModeCommand{ControlMode::remote_control});
  expect(result.error == Error::value_out_of_range, "host cannot command RC mode");

  result = skid.encode(ClearErrorCommand{4});
  expect(result.frame.id == 0x441 && result.frame.size == 1 && result.frame.data[0] == 4,
         "clear motor error");
  result = skid.encode(ClearErrorCommand{5});
  expect(result.error == Error::value_out_of_range, "clear-error motor range");

  result = skid.encode(VersionRequest{});
  expect(result.frame.id == 0x411 && result.frame.size == 1 && result.frame.data[0] == 1,
         "version query uses documented ID and DLC");

  ModelCommandPtr foreign_command = std::make_shared<ForeignModelCommand>();
  result = skid.encode(Command{std::move(foreign_command)});
  expect(result.error == Error::unsupported_command,
         "profile-specific extension is rejected by the wrong codec");
}

void test_core_feedback() {
  using namespace agilex::ugv;
  ScoutMiniCodec codec;

  auto result = codec.decode(CanFrame{0x211, 8, {2, 1, 0x01, 0x01, 0x01, 0x04, 0, 9}});
  const auto& system = decoded_as<SystemState>(result);
  expect(system.vehicle_state == VehicleState::exception, "vehicle state");
  expect(system.control_mode == ControlMode::can, "control mode");
  expect(near(system.battery_voltage_v, 25.7), "battery scale");
  expect(system.error_flags == 0x0104, "16-bit error bitmap");
  expect(system.count == 9, "system count");

  result = codec.decode(CanFrame{0x221, 8, {0xFF, 0x9C, 0x00, 0xC8,
                                                    0xFF, 0x38, 0xAA, 0x55}});
  const auto& motion = decoded_as<MotionState>(result);
  expect(near(motion.linear_velocity_mps, -0.1), "negative linear feedback");
  expect(near(motion.angular_velocity_radps, 0.2), "angular feedback");
  expect(near(motion.lateral_velocity_mps, -0.2), "lateral feedback");

  result = codec.decode(CanFrame{0x231, 8, {1, 3, 0x4A, 3, 0x29, 0, 0, 0xFE}});
  const auto& lights = decoded_as<LightState>(result);
  expect(lights.enabled && lights.front_value == 0x4A && lights.rear_value == 0x29,
         "light feedback values remain raw");
  expect(lights.count == 0xFE, "light count");

  result = codec.decode(CanFrame{0x241, 8, {0xE6, 0xFF, 2, 0xFD, 4, 0xFB, 0, 0xFF}});
  const auto& remote = decoded_as<RemoteControlState>(result);
  expect(remote.swa == 2 && remote.swb == 1 && remote.swc == 2 && remote.swd == 3,
         "remote switch bit fields");
  expect(remote.right_horizontal == -1 && remote.left_vertical == -3 && remote.knob == -5,
         "remote signed axes");
  expect(remote.count == 0xFF, "remote count");

  result = codec.decode(CanFrame{0x311, 8, {0xFF, 0xFF, 0xFC, 0x18,
                                                    0x00, 0x00, 0x03, 0xE8}});
  const auto& odometry = decoded_as<OdometryState>(result);
  expect(odometry.left_distance_mm == -1000 && odometry.right_distance_mm == 1000,
         "signed 32-bit odometry");

  result = codec.decode(CanFrame{0x41A, 8, {1, 2, 3, 4, 5, 6, 7, 8}});
  const auto& version = decoded_as<VersionInfo>(result);
  expect(version.controller_hardware_major == 1 &&
             version.controller_software_minor == 6 && version.driver_software_minor == 8,
         "version feedback uses 0x41A");
}

void test_actuator_feedback_and_validation() {
  using namespace agilex::ugv;
  ScoutMiniCodec codec;

  auto result = codec.decode(CanFrame{0x253, 8, {0xFF, 0x9C, 0x00, 0x7B,
                                                    0xDE, 0xAD, 0xBE, 0xEF}});
  const auto& high = decoded_as<ActuatorHighSpeedState>(result);
  expect(high.index == 3 && high.speed_rpm == -100 && near(high.current_a, 12.3),
         "actuator high-speed fields; reserved bytes ignored");

  result = codec.decode(CanFrame{0x264, 8, {0x01, 0x01, 0xFF, 0xF6,
                                                    0xFB, 0x05, 0xAA, 0x55}});
  const auto& low = decoded_as<ActuatorLowSpeedState>(result);
  expect(low.index == 4 && near(low.driver_voltage_v, 25.7), "actuator low voltage");
  expect(low.driver_temperature_c == -10 && low.motor_temperature_c == -5 &&
             low.status_flags == 5,
         "actuator temperatures and status");

  result = codec.decode(CanFrame{0x211, 7, {}});
  expect(result.status == DecodeStatus::invalid_dlc, "strict feedback DLC");
  result = codec.decode(CanFrame{0x700, 8, {}});
  expect(result.status == DecodeStatus::ignored, "unknown standard frame ignored");
  result = codec.decode(CanFrame{0x800, 8, {}});
  expect(result.status == DecodeStatus::invalid_frame, "extended ID rejected");
}

}  // namespace

int main() {
  test_commands();
  test_core_feedback();
  test_actuator_feedback_and_validation();
  std::cout << "all Scout Mini codec tests passed\n";
}
