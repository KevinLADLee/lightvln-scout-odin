// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <memory>
#include <mutex>
#include <thread>

#include "agilex_ugv_sdk/transport/can_transport.hpp"

namespace agilex::ugv {

class SocketCanTransport final : public CanTransport {
 public:
  SocketCanTransport() = default;
  ~SocketCanTransport() override;

  SocketCanTransport(const SocketCanTransport&) = delete;
  SocketCanTransport& operator=(const SocketCanTransport&) = delete;
  SocketCanTransport(SocketCanTransport&&) = delete;
  SocketCanTransport& operator=(SocketCanTransport&&) = delete;

  [[nodiscard]] std::error_code open(std::string_view interface_name) override;
  void close() noexcept override;
  [[nodiscard]] bool is_open() const noexcept override;
  [[nodiscard]] std::error_code send(const CanFrame& frame) override;
  void set_receive_handler(ReceiveHandler handler) override;

 private:
  struct Connection;
  static void receive_loop(const std::shared_ptr<Connection>& connection) noexcept;

  mutable std::mutex mutex_;
  std::shared_ptr<Connection> connection_;
  std::thread receive_thread_;
  ReceiveHandler receive_handler_;
};

[[nodiscard]] CanTransportPtr make_socketcan_transport();

}  // namespace agilex::ugv
