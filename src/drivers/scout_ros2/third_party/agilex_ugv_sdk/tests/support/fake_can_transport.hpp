// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <string>
#include <utility>
#include <vector>

#include "agilex_ugv_sdk/transport/can_transport.hpp"

namespace agilex::ugv::testing {

class FakeCanTransport final : public CanTransport {
 public:
  std::error_code open(std::string_view interface_name) override {
    if (open_error) return open_error;
    interface = std::string{interface_name};
    opened = true;
    return {};
  }

  void close() noexcept override { opened = false; }
  bool is_open() const noexcept override { return opened; }

  std::error_code send(const CanFrame& frame) override {
    if (send_error) return send_error;
    sent.push_back(frame);
    return {};
  }

  void set_receive_handler(ReceiveHandler value) override {
    handler = std::move(value);
  }

  void inject(const CanFrame& frame) { handler(frame); }

  bool opened{false};
  std::string interface;
  std::vector<CanFrame> sent;
  ReceiveHandler handler;
  std::error_code open_error;
  std::error_code send_error;
};

}  // namespace agilex::ugv::testing
