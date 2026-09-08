// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <functional>
#include <memory>
#include <string_view>
#include <system_error>

#include "agilex_ugv_sdk/transport/can_frame.hpp"

namespace agilex::ugv {

class CanTransport {
 public:
  using ReceiveHandler = std::function<void(const CanFrame&)>;

  virtual ~CanTransport() = default;

  [[nodiscard]] virtual std::error_code open(std::string_view interface_name) = 0;
  virtual void close() noexcept = 0;
  [[nodiscard]] virtual bool is_open() const noexcept = 0;
  [[nodiscard]] virtual std::error_code send(const CanFrame& frame) = 0;
  virtual void set_receive_handler(ReceiveHandler handler) = 0;
};

using CanTransportPtr = std::unique_ptr<CanTransport>;

}  // namespace agilex::ugv
