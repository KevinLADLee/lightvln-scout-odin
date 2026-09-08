// SPDX-License-Identifier: Apache-2.0

#include <chrono>
#include <iostream>
#include <string_view>
#include <thread>

#include "agilex_ugv_sdk/models/scout/scout_mini.hpp"

int main(int argc, char** argv) {
  if (argc != 2) {
    std::cerr << "usage: scout_mini_state <can-interface>\n";
    return 2;
  }

  agilex::ugv::ScoutMini robot;
  if (const auto error = robot.connect(argv[1])) {
    std::cerr << "connect failed: " << error.message() << '\n';
    return 1;
  }

  for (;;) {
    const auto state = robot.state();
    if (state.system) {
      std::cout << "battery=" << state.system->battery_voltage_v
                << " V, error_flags=0x" << std::hex
                << state.system->error_flags << std::dec << '\n';
    }
    std::this_thread::sleep_for(std::chrono::seconds(1));
  }
}
