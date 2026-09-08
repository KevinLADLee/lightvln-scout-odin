// SPDX-License-Identifier: Apache-2.0

#include "agilex_ugv_sdk/models/scout/scout_mini.hpp"

#include <utility>

namespace agilex::ugv {

ScoutMini::ScoutMini(ScoutMiniVariant variant, CanTransportPtr transport)
    : robot_(make_scout_mini_codec(variant), std::move(transport)) {}

std::error_code ScoutMini::connect(std::string_view interface_name) {
  return robot_.connect(interface_name);
}

void ScoutMini::disconnect() noexcept { robot_.disconnect(); }

bool ScoutMini::is_connected() const noexcept { return robot_.is_connected(); }

std::error_code ScoutMini::set_control_mode(ControlMode mode) {
  return robot_.send(ControlModeCommand{mode});
}

std::error_code ScoutMini::set_motion(const MotionCommand& command) {
  return robot_.send(command);
}

std::error_code ScoutMini::stop() { return set_motion(MotionCommand{}); }

std::error_code ScoutMini::set_lights(const LightCommand& command) {
  return robot_.send(command);
}

std::error_code ScoutMini::clear_error(std::uint8_t motor) {
  return robot_.send(ClearErrorCommand{motor});
}

std::error_code ScoutMini::request_version() {
  return robot_.send(VersionRequest{});
}

StateSnapshot ScoutMini::state() const { return robot_.state(); }

void ScoutMini::set_feedback_handler(Robot::FeedbackHandler handler) {
  robot_.set_feedback_handler(std::move(handler));
}

}  // namespace agilex::ugv
