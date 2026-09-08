// SPDX-License-Identifier: Apache-2.0

#pragma once

#include "agilex_ugv_sdk/protocol/protocol_codec.hpp"

namespace agilex::ugv {

enum class ScoutMiniVariant {
  skid_steer,
  omni,
};

class ScoutMiniCodec final : public ProtocolCodec {
 public:
  explicit ScoutMiniCodec(ScoutMiniVariant variant = ScoutMiniVariant::skid_steer)
      : variant_(variant) {}

  [[nodiscard]] ModelCapabilities capabilities() const noexcept override;
  [[nodiscard]] EncodeResult encode(const Command& command) override;
  [[nodiscard]] DecodeResult decode(const CanFrame& frame) const override;

 private:
  ScoutMiniVariant variant_;
  std::uint8_t light_count_{0};
};

[[nodiscard]] ProtocolCodecPtr make_scout_mini_codec(
    ScoutMiniVariant variant = ScoutMiniVariant::skid_steer);

}  // namespace agilex::ugv
