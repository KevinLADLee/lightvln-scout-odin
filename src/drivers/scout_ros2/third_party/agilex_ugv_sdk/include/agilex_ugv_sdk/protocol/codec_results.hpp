// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <optional>
#include <system_error>

#include "agilex_ugv_sdk/core/feedback.hpp"
#include "agilex_ugv_sdk/transport/can_frame.hpp"

namespace agilex::ugv {

struct EncodeResult {
  CanFrame frame{};
  std::error_code error{};

  [[nodiscard]] explicit operator bool() const noexcept { return !error; }
};

enum class DecodeStatus {
  decoded,
  ignored,
  invalid_frame,
  invalid_dlc,
};

struct DecodeResult {
  DecodeStatus status{DecodeStatus::ignored};
  std::optional<Feedback> feedback{};

  [[nodiscard]] explicit operator bool() const noexcept {
    return status == DecodeStatus::decoded && feedback.has_value();
  }
};

}  // namespace agilex::ugv
