// SPDX-License-Identifier: Apache-2.0

#include "agilex_ugv_sdk/core/error.hpp"

#include <string>

namespace agilex::ugv {
namespace {

class AgilexErrorCategory final : public std::error_category {
 public:
  [[nodiscard]] const char* name() const noexcept override {
    return "agilex_ugv_sdk";
  }

  [[nodiscard]] std::string message(int value) const override {
    switch (static_cast<Error>(value)) {
      case Error::success:
        return "success";
      case Error::invalid_argument:
        return "invalid argument";
      case Error::value_out_of_range:
        return "value out of range";
      case Error::unsupported_command:
        return "command is not supported by this vehicle profile";
      case Error::invalid_frame:
        return "invalid CAN frame";
      case Error::invalid_dlc:
        return "unexpected CAN payload length";
      case Error::not_connected:
        return "CAN transport is not connected";
      case Error::already_connected:
        return "CAN transport is already connected";
    }
    return "unknown agilex_ugv_sdk error";
  }
};

}  // namespace

const std::error_category& error_category() noexcept {
  static const AgilexErrorCategory category;
  return category;
}

std::error_code make_error_code(Error error) noexcept {
  return {static_cast<int>(error), error_category()};
}

}  // namespace agilex::ugv
