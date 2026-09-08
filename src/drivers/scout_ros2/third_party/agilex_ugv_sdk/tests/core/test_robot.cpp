// SPDX-License-Identifier: Apache-2.0

#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string_view>
#include <system_error>
#include <utility>
#include <variant>

#include "agilex_ugv_sdk/core/robot.hpp"
#include "support/assertions.hpp"
#include "support/fake_can_transport.hpp"

namespace {

using namespace agilex::ugv;
using testing::expect;
using testing::FakeCanTransport;

class AuxiliaryCommand final : public ModelCommand {
 public:
  explicit AuxiliaryCommand(std::uint8_t value) : value(value) {}
  std::uint8_t value;
};

class AuxiliaryFeedback final : public ModelFeedback {};

class TestCodec final : public ProtocolCodec {
 public:
  TestCodec(std::string_view name, std::uint32_t id) : name_(name), id_(id) {}

  ModelCapabilities capabilities() const noexcept override {
    return {name_, 0, false, false};
  }

  EncodeResult encode(const Command& command) override {
    if (const auto* extension = std::get_if<ModelCommandPtr>(&command)) {
      const auto auxiliary =
          std::dynamic_pointer_cast<const AuxiliaryCommand>(*extension);
      if (auxiliary) {
        return {CanFrame{id_, 1, {auxiliary->value}}, {}};
      }
    }
    return {{}, Error::unsupported_command};
  }

  DecodeResult decode(const CanFrame& frame) const override {
    if (!frame.valid()) return {DecodeStatus::invalid_frame, std::nullopt};
    if (frame.id == id_ + 1U) {
      if (frame.size != 1U) return {DecodeStatus::invalid_dlc, std::nullopt};
      SystemState state;
      state.battery_voltage_v = frame.data[0];
      return {DecodeStatus::decoded, Feedback{state}};
    }
    if (frame.id == id_ + 2U) {
      ModelFeedbackPtr extension = std::make_shared<AuxiliaryFeedback>();
      return {DecodeStatus::decoded, Feedback{std::move(extension)}};
    }
    return {};
  }

 private:
  std::string_view name_;
  std::uint32_t id_;
};

void exercise_model(std::string_view name, std::uint32_t id) {
  auto transport = std::make_unique<FakeCanTransport>();
  auto* fake = transport.get();
  Robot robot{std::make_unique<TestCodec>(name, id), std::move(transport)};

  expect(robot.capabilities().model_name == name, "capabilities come from codec");
  expect(robot.send(VersionRequest{}) == Error::not_connected,
         "disconnected commands fail before encoding");
  fake->open_error = std::make_error_code(std::errc::permission_denied);
  expect(robot.connect("fake-can") == fake->open_error,
         "connection errors propagate");
  expect(!robot.is_connected(), "failed open leaves transport disconnected");
  fake->open_error.clear();
  expect(!robot.connect("fake-can"), "connection succeeds after error clears");

  ModelCommandPtr extension = std::make_shared<AuxiliaryCommand>(42);
  expect(!robot.send(extension), "custom model command accepted by its codec");
  expect(fake->sent.size() == 1 && fake->sent.back().id == id &&
             fake->sent.back().data[0] == 42,
         "injected codec determines the wire format");
  expect(robot.send(VersionRequest{}) == Error::unsupported_command,
         "codec errors propagate without sending a frame");
  fake->send_error = std::make_error_code(std::errc::io_error);
  expect(robot.send(extension) == fake->send_error, "transport errors propagate");
  expect(fake->sent.size() == 1, "failed commands do not add frames");

  int callbacks = 0;
  bool received_extension = false;
  robot.set_feedback_handler([&](const Feedback& feedback) {
    ++callbacks;
    if (const auto* value = std::get_if<ModelFeedbackPtr>(&feedback)) {
      received_extension =
          std::dynamic_pointer_cast<const AuxiliaryFeedback>(*value) != nullptr;
    }
  });
  fake->inject(CanFrame{id + 1U, 1, {24}});
  expect(robot.state().system && robot.state().system->battery_voltage_v == 24,
         "common feedback updates the snapshot");
  fake->inject(CanFrame{id + 1U, 0, {}});
  fake->inject(CanFrame{0x700, 8, {}});
  expect(callbacks == 1, "invalid and unknown frames do not reach consumers");
  fake->inject(CanFrame{id + 2U, 1, {}});
  expect(received_extension && callbacks == 2, "model feedback reaches callback");

  robot.disconnect();
  expect(!robot.is_connected(), "disconnect closes transport");
  expect(!robot.connect("fake-can"), "reconnect succeeds");
  expect(!robot.state().system && !robot.state().updated_at,
         "reconnect clears previous feedback");
}

}  // namespace

int main() {
  exercise_model("test-model-a", 0x600);
  exercise_model("test-model-b", 0x650);
}
