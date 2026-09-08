// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <cstdint>
#include <string_view>

namespace agilex::ugv {

struct ModelCapabilities {
  std::string_view model_name;
  std::uint8_t actuator_count{0};
  bool supports_lateral_motion{false};
  bool supports_lights{false};
};

}  // namespace agilex::ugv
