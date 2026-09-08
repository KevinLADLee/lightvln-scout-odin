// SPDX-License-Identifier: Apache-2.0

#include <cstdlib>
#include <iostream>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

#include "agilex_ugv_sdk/core/error.hpp"
#include "agilex_ugv_sdk/models/scout/scout_mini.hpp"
#include "support/assertions.hpp"
#include "support/fake_can_transport.hpp"

using agilex::ugv::testing::expect;
using agilex::ugv::testing::FakeCanTransport;

int main() {
  using namespace agilex::ugv;

  auto transport = std::make_unique<FakeCanTransport>();
  auto* fake = transport.get();
  ScoutMini robot{ScoutMiniVariant::skid_steer, std::move(transport)};

  expect(robot.stop() == Error::not_connected, "send requires a connection");
  expect(!robot.connect("vcan-test"), "connect succeeds");
  expect(fake->interface == "vcan-test" && robot.is_connected(), "transport opened");

  expect(!robot.set_control_mode(ControlMode::can), "send control mode");
  expect(fake->sent.size() == 1 && fake->sent.back().id == 0x421 &&
             fake->sent.back().size == 1,
         "facade sends encoded frame");

  int callbacks = 0;
  robot.set_feedback_handler([&callbacks](const Feedback&) { ++callbacks; });
  fake->inject(CanFrame{0x211, 8, {0, 1, 0, 240, 0, 0, 0, 7}});
  fake->inject(CanFrame{0x252, 8, {0, 10, 0, 20, 0, 0, 0, 0}});
  fake->inject(CanFrame{0x123, 8, {}});

  const auto state = robot.state();
  expect(state.system.has_value() && state.system->control_mode == ControlMode::can,
         "system feedback stored");
  expect(state.actuators_high_speed[1].has_value() &&
             state.actuators_high_speed[1]->speed_rpm == 10,
         "actuator indexed into snapshot");
  expect(state.updated_at.has_value(), "snapshot timestamped");
  expect(callbacks == 2, "only decoded feedback triggers callback");

  robot.disconnect();
  expect(!robot.is_connected(), "disconnect closes transport");
  expect(!robot.connect("vcan-test"), "reconnect succeeds");
  expect(!robot.state().updated_at.has_value(), "reconnect clears stale state");
  robot.disconnect();
  std::cout << "all Scout Mini robot tests passed\n";
}
