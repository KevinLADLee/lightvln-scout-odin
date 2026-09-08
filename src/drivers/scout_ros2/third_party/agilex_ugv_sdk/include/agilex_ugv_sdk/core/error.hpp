// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <system_error>
#include <type_traits>

namespace agilex::ugv {

enum class Error {
  success = 0,
  invalid_argument,
  value_out_of_range,
  unsupported_command,
  invalid_frame,
  invalid_dlc,
  not_connected,
  already_connected,
};

const std::error_category& error_category() noexcept;
std::error_code make_error_code(Error error) noexcept;

}  // namespace agilex::ugv

namespace std {
template <>
struct is_error_code_enum<agilex::ugv::Error> : true_type {};
}  // namespace std
