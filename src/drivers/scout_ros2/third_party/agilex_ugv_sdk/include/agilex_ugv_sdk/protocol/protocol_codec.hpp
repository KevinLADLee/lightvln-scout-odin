// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <memory>

#include "agilex_ugv_sdk/core/commands.hpp"
#include "agilex_ugv_sdk/core/error.hpp"
#include "agilex_ugv_sdk/core/model_capabilities.hpp"
#include "agilex_ugv_sdk/protocol/codec_results.hpp"

namespace agilex::ugv {

class ProtocolCodec {
 public:
  virtual ~ProtocolCodec() = default;

  [[nodiscard]] virtual ModelCapabilities capabilities() const noexcept = 0;
  [[nodiscard]] virtual EncodeResult encode(const Command& command) = 0;
  [[nodiscard]] virtual DecodeResult decode(const CanFrame& frame) const = 0;
};

using ProtocolCodecPtr = std::unique_ptr<ProtocolCodec>;

}  // namespace agilex::ugv
