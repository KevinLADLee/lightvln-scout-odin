// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <functional>
#include <mutex>
#include <string_view>
#include <system_error>

#include "agilex_ugv_sdk/core/state_snapshot.hpp"
#include "agilex_ugv_sdk/protocol/protocol_codec.hpp"
#include "agilex_ugv_sdk/transport/can_transport.hpp"

namespace agilex::ugv {

class Robot {
 public:
  using FeedbackHandler = std::function<void(const Feedback&)>;

  Robot(ProtocolCodecPtr codec, CanTransportPtr transport);
  ~Robot();

  Robot(const Robot&) = delete;
  Robot& operator=(const Robot&) = delete;
  Robot(Robot&&) = delete;
  Robot& operator=(Robot&&) = delete;

  [[nodiscard]] std::error_code connect(std::string_view interface_name);
  void disconnect() noexcept;
  [[nodiscard]] bool is_connected() const noexcept;
  [[nodiscard]] std::error_code send(const Command& command);

  [[nodiscard]] ModelCapabilities capabilities() const noexcept;
  [[nodiscard]] StateSnapshot state() const;
  void set_feedback_handler(FeedbackHandler handler);

 private:
  void handle_frame(const CanFrame& frame);
  void update_state(const Feedback& feedback);

  ProtocolCodecPtr codec_;
  CanTransportPtr transport_;
  std::mutex codec_mutex_;
  mutable std::mutex state_mutex_;
  StateSnapshot state_;
  mutable std::mutex handler_mutex_;
  FeedbackHandler feedback_handler_;
};

}  // namespace agilex::ugv
