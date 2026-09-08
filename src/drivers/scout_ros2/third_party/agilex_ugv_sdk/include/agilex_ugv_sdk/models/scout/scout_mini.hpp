// SPDX-License-Identifier: Apache-2.0

#pragma once

#include "agilex_ugv_sdk/models/scout/scout_mini_codec.hpp"
#include "agilex_ugv_sdk/core/robot.hpp"
#include "agilex_ugv_sdk/transport/socketcan_transport.hpp"

namespace agilex::ugv {

class ScoutMini final {
 public:
  explicit ScoutMini(
      ScoutMiniVariant variant = ScoutMiniVariant::skid_steer,
      CanTransportPtr transport = make_socketcan_transport());

  [[nodiscard]] std::error_code connect(std::string_view interface_name);
  void disconnect() noexcept;
  [[nodiscard]] bool is_connected() const noexcept;

  [[nodiscard]] std::error_code set_control_mode(ControlMode mode);
  [[nodiscard]] std::error_code set_motion(const MotionCommand& command);
  [[nodiscard]] std::error_code stop();
  [[nodiscard]] std::error_code set_lights(const LightCommand& command);
  [[nodiscard]] std::error_code clear_error(std::uint8_t motor = 0);
  [[nodiscard]] std::error_code request_version();

  [[nodiscard]] StateSnapshot state() const;
  void set_feedback_handler(Robot::FeedbackHandler handler);

 private:
  Robot robot_;
};

}  // namespace agilex::ugv
