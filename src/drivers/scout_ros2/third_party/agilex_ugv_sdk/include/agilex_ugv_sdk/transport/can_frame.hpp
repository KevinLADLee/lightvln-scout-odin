// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace agilex::ugv {

struct CanFrame {
  static constexpr std::size_t kMaxPayloadSize = 8;

  std::uint32_t id{0};
  std::uint8_t size{0};
  std::array<std::uint8_t, kMaxPayloadSize> data{};

  [[nodiscard]] constexpr bool valid() const noexcept {
    return id <= 0x7FFU && size <= kMaxPayloadSize;
  }
};

}  // namespace agilex::ugv
