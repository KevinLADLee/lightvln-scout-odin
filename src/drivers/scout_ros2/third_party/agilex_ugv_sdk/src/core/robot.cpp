// SPDX-License-Identifier: Apache-2.0

#include "agilex_ugv_sdk/core/robot.hpp"

#include <chrono>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace agilex::ugv {
namespace {

template <class... Ts>
struct Overloaded : Ts... {
  using Ts::operator()...;
};
template <class... Ts>
Overloaded(Ts...) -> Overloaded<Ts...>;

}  // namespace

Robot::Robot(ProtocolCodecPtr codec, CanTransportPtr transport)
    : codec_(std::move(codec)), transport_(std::move(transport)) {
  if (!codec_ || !transport_) {
    throw std::invalid_argument("Robot requires a codec and a CAN transport");
  }
  transport_->set_receive_handler(
      [this](const CanFrame& frame) { handle_frame(frame); });
}

Robot::~Robot() { disconnect(); }

std::error_code Robot::connect(std::string_view interface_name) {
  const auto error = transport_->open(interface_name);
  if (!error) {
    std::lock_guard<std::mutex> lock(state_mutex_);
    state_ = {};
  }
  return error;
}

void Robot::disconnect() noexcept { transport_->close(); }

bool Robot::is_connected() const noexcept { return transport_->is_open(); }

std::error_code Robot::send(const Command& command) {
  if (!is_connected()) {
    return Error::not_connected;
  }
  EncodeResult result;
  {
    std::lock_guard<std::mutex> lock(codec_mutex_);
    result = codec_->encode(command);
  }
  if (!result) {
    return result.error;
  }
  return transport_->send(result.frame);
}

ModelCapabilities Robot::capabilities() const noexcept {
  return codec_->capabilities();
}

StateSnapshot Robot::state() const {
  std::lock_guard<std::mutex> lock(state_mutex_);
  return state_;
}

void Robot::set_feedback_handler(FeedbackHandler handler) {
  std::lock_guard<std::mutex> lock(handler_mutex_);
  feedback_handler_ = std::move(handler);
}

void Robot::handle_frame(const CanFrame& frame) {
  const auto result = codec_->decode(frame);
  if (!result) return;

  const auto& feedback = *result.feedback;
  update_state(feedback);

  FeedbackHandler handler;
  {
    std::lock_guard<std::mutex> lock(handler_mutex_);
    handler = feedback_handler_;
  }
  if (handler) handler(feedback);
}

void Robot::update_state(const Feedback& feedback) {
  std::lock_guard<std::mutex> lock(state_mutex_);
  std::visit(
      Overloaded{
          [this](const SystemState& value) { state_.system = value; },
          [this](const MotionState& value) { state_.motion = value; },
          [this](const LightState& value) { state_.lights = value; },
          [this](const RemoteControlState& value) {
            state_.remote_control = value;
          },
          [this](const ActuatorHighSpeedState& value) {
            if (value.index >= 1U &&
                value.index <= state_.actuators_high_speed.size()) {
              state_.actuators_high_speed[value.index - 1U] = value;
            }
          },
          [this](const ActuatorLowSpeedState& value) {
            if (value.index >= 1U &&
                value.index <= state_.actuators_low_speed.size()) {
              state_.actuators_low_speed[value.index - 1U] = value;
            }
          },
          [this](const OdometryState& value) { state_.odometry = value; },
          [this](const VersionInfo& value) { state_.version = value; },
          [](const ModelFeedbackPtr&) {}},
      feedback);
  state_.updated_at = std::chrono::steady_clock::now();
}

}  // namespace agilex::ugv
