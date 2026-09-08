// SPDX-License-Identifier: Apache-2.0

#include "agilex_ugv_sdk/transport/socketcan_transport.hpp"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstring>
#include <system_error>
#include <utility>

#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#include "agilex_ugv_sdk/core/error.hpp"

namespace agilex::ugv {

struct SocketCanTransport::Connection {
  std::atomic<int> socket{-1};
  std::atomic<bool> running{false};
  std::mutex write_mutex;
  std::mutex handler_mutex;
  ReceiveHandler handler;
};

SocketCanTransport::~SocketCanTransport() { close(); }

std::error_code SocketCanTransport::open(std::string_view interface_name) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (connection_) {
    return Error::already_connected;
  }
  if (interface_name.empty() || interface_name.size() >= IFNAMSIZ) {
    return Error::invalid_argument;
  }

  const int descriptor = ::socket(PF_CAN, SOCK_RAW, CAN_RAW);
  if (descriptor < 0) {
    return {errno, std::system_category()};
  }

  ifreq request{};
  std::memcpy(request.ifr_name, interface_name.data(), interface_name.size());
  request.ifr_name[interface_name.size()] = '\0';
  if (::ioctl(descriptor, SIOCGIFINDEX, &request) < 0) {
    const std::error_code error{errno, std::system_category()};
    ::close(descriptor);
    return error;
  }

  sockaddr_can address{};
  address.can_family = AF_CAN;
  address.can_ifindex = request.ifr_ifindex;
  if (::bind(descriptor, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0) {
    const std::error_code error{errno, std::system_category()};
    ::close(descriptor);
    return error;
  }

  auto connection = std::make_shared<Connection>();
  connection->socket.store(descriptor);
  connection->running.store(true);
  connection->handler = receive_handler_;
  try {
    receive_thread_ = std::thread(&SocketCanTransport::receive_loop, connection);
  } catch (...) {
    connection->running.store(false);
    connection->socket.store(-1);
    ::close(descriptor);
    throw;
  }
  connection_ = std::move(connection);
  return {};
}

void SocketCanTransport::close() noexcept {
  std::shared_ptr<Connection> connection;
  std::thread receive_thread;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    connection = std::move(connection_);
    if (receive_thread_.joinable()) {
      receive_thread = std::move(receive_thread_);
    }
  }

  if (connection) {
    connection->running.store(false);
    std::lock_guard<std::mutex> lock(connection->write_mutex);
    const int descriptor = connection->socket.exchange(-1);
    if (descriptor >= 0) {
      ::shutdown(descriptor, SHUT_RDWR);
      ::close(descriptor);
    }
  }

  if (receive_thread.joinable()) {
    if (receive_thread.get_id() == std::this_thread::get_id()) {
      receive_thread.detach();
    } else {
      receive_thread.join();
    }
  }
}

bool SocketCanTransport::is_open() const noexcept {
  std::lock_guard<std::mutex> lock(mutex_);
  return connection_ && connection_->socket.load() >= 0;
}

std::error_code SocketCanTransport::send(const CanFrame& frame) {
  if (!frame.valid()) {
    return Error::invalid_frame;
  }

  std::shared_ptr<Connection> connection;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    connection = connection_;
  }
  if (!connection) {
    return Error::not_connected;
  }

  std::lock_guard<std::mutex> lock(connection->write_mutex);
  const int descriptor = connection->socket.load();
  if (descriptor < 0) {
    return Error::not_connected;
  }

  can_frame native{};
  native.can_id = frame.id;
  native.can_dlc = frame.size;
  std::copy_n(frame.data.begin(), frame.size, native.data);
  const auto written = ::write(descriptor, &native, sizeof(native));
  if (written != static_cast<ssize_t>(sizeof(native))) {
    return {errno == 0 ? EIO : errno, std::system_category()};
  }
  return {};
}

void SocketCanTransport::set_receive_handler(ReceiveHandler handler) {
  std::shared_ptr<Connection> connection;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    receive_handler_ = handler;
    connection = connection_;
  }
  if (connection) {
    std::lock_guard<std::mutex> lock(connection->handler_mutex);
    connection->handler = std::move(handler);
  }
}

void SocketCanTransport::receive_loop(
    const std::shared_ptr<Connection>& connection) noexcept {
  while (connection->running.load()) {
    can_frame native{};
    const int descriptor = connection->socket.load();
    if (descriptor < 0) break;

    const auto received = ::read(descriptor, &native, sizeof(native));
    if (received != static_cast<ssize_t>(sizeof(native))) {
      if (errno == EINTR) continue;
      break;
    }
    if (!connection->running.load()) break;
    if ((native.can_id & (CAN_EFF_FLAG | CAN_RTR_FLAG | CAN_ERR_FLAG)) != 0U) {
      continue;
    }

    CanFrame frame;
    frame.id = native.can_id & CAN_SFF_MASK;
    frame.size = native.can_dlc;
    std::copy_n(native.data, frame.size, frame.data.begin());

    ReceiveHandler handler;
    {
      std::lock_guard<std::mutex> lock(connection->handler_mutex);
      handler = connection->handler;
    }
    if (handler) {
      try {
        handler(frame);
      } catch (...) {
        // User callbacks must not terminate the transport receive thread.
      }
    }
  }
  connection->running.store(false);
}

CanTransportPtr make_socketcan_transport() {
  return std::make_unique<SocketCanTransport>();
}

}  // namespace agilex::ugv
