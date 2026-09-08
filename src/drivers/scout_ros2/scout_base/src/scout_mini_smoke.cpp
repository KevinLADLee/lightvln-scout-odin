// SPDX-License-Identifier: Apache-2.0

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <memory>
#include <string>
#include <system_error>

#include "agilex_ugv_sdk/models/scout/scout_mini.hpp"
#include "rclcpp/rclcpp.hpp"

namespace scout_base
{
namespace
{

using agilex::ugv::ControlMode;
using agilex::ugv::MotionCommand;
using agilex::ugv::ScoutMini;
using agilex::ugv::StateSnapshot;
using agilex::ugv::VehicleState;
using namespace std::chrono_literals;

class ScoutMiniSmokeNode final : public rclcpp::Node
{
public:
  ScoutMiniSmokeNode()
  : Node("scout_mini_smoke")
  {
    can_interface_ = declare_parameter<std::string>("can_interface", "can0");
    run_motion_test_ = declare_parameter<bool>("run_motion_test", false);
    linear_velocity_mps_ =
      declare_parameter<double>("linear_velocity_mps", 0.05);
    angular_velocity_radps_ =
      declare_parameter<double>("angular_velocity_radps", 0.10);
    segment_duration_s_ =
      declare_parameter<double>("segment_duration_s", 0.60);

    if (!parameters_are_safe()) {
      finish(false, "invalid or unsafe motion-test parameters");
      return;
    }

    if (const auto error = robot_.connect(can_interface_)) {
      finish(false, "cannot open " + can_interface_ + ": " + error.message());
      return;
    }

    RCLCPP_INFO(
      get_logger(), "connected to %s; motion test: %s",
      can_interface_.c_str(), run_motion_test_ ? "enabled" : "disabled");
    if (!send_checked(robot_.request_version(), "request version")) {return;}
    phase_started_at_ = std::chrono::steady_clock::now();
    timer_ = create_wall_timer(20ms, [this] {tick();});
  }

  ~ScoutMiniSmokeNode() override {make_safe();}

  [[nodiscard]] bool passed() const noexcept {return passed_;}

private:
  enum class Phase
  {
    wait_for_feedback,
    settle,
    forward,
    stop_after_forward,
    rotate,
    stop_after_rotate,
    verify_stopped,
    complete,
  };

  [[nodiscard]] bool parameters_are_safe() const noexcept
  {
    return !can_interface_.empty() && std::isfinite(linear_velocity_mps_) &&
           std::isfinite(angular_velocity_radps_) &&
           std::isfinite(segment_duration_s_) && linear_velocity_mps_ > 0.0 &&
           linear_velocity_mps_ <= 0.10 && angular_velocity_radps_ > 0.0 &&
           angular_velocity_radps_ <= 0.20 && segment_duration_s_ >= 0.20 &&
           segment_duration_s_ <= 2.0;
  }

  void tick()
  {
    if (phase_ == Phase::complete) {return;}

    const auto snapshot = robot_.state();
    if (snapshot.motion) {
      if (phase_ == Phase::forward) {
        max_linear_feedback_mps_ =
          std::max(
          max_linear_feedback_mps_,
          std::abs(snapshot.motion->linear_velocity_mps));
      } else if (phase_ == Phase::rotate) {
        max_angular_feedback_radps_ =
          std::max(
          max_angular_feedback_radps_,
          std::abs(snapshot.motion->angular_velocity_radps));
      }
    }

    switch (phase_) {
      case Phase::wait_for_feedback:
        wait_for_feedback(snapshot);
        break;
      case Phase::settle:
        if (!send_motion({})) {return;}
        if (elapsed() >= 0.40) {enter(Phase::forward, "forward");}
        break;
      case Phase::forward:
        if (!send_motion({linear_velocity_mps_, 0.0, 0.0})) {return;}
        if (elapsed() >= segment_duration_s_) {
          enter(Phase::stop_after_forward, "stop after forward");
        }
        break;
      case Phase::stop_after_forward:
        if (!send_motion({})) {return;}
        if (elapsed() >= 0.40) {enter(Phase::rotate, "rotate in place");}
        break;
      case Phase::rotate:
        if (!send_motion({0.0, angular_velocity_radps_, 0.0})) {return;}
        if (elapsed() >= segment_duration_s_) {
          enter(Phase::stop_after_rotate, "final stop");
        }
        break;
      case Phase::stop_after_rotate:
        if (!send_motion({})) {return;}
        if (elapsed() >= 0.60) {
          enter(Phase::verify_stopped, "verify stopped state");
        }
        break;
      case Phase::verify_stopped:
        verify_final_state(snapshot);
        break;
      case Phase::complete:
        break;
    }
  }

  void wait_for_feedback(const StateSnapshot & snapshot)
  {
    if (snapshot.version && snapshot.system && snapshot.motion) {
      const auto & version = *snapshot.version;
      RCLCPP_INFO(
        get_logger(),
        "controller HW %u.%u SW %u.%u; driver HW %u.%u SW %u.%u; battery %.1f V",
        version.controller_hardware_major, version.controller_hardware_minor,
        version.controller_software_major, version.controller_software_minor,
        version.driver_hardware_major, version.driver_hardware_minor,
        version.driver_software_major, version.driver_software_minor,
        snapshot.system->battery_voltage_v);

      if (!run_motion_test_) {
        finish(true, "read-only CAN diagnostic passed");
        return;
      }
      if (snapshot.system->vehicle_state != VehicleState::normal ||
        snapshot.system->error_flags != 0U)
      {
        finish(false, "robot reports a non-normal state or active fault");
        return;
      }
      if (!send_checked(
          robot_.set_control_mode(ControlMode::can),
          "enter CAN control mode"))
      {
        return;
      }
      enter(Phase::settle, "zero-speed settle");
      return;
    }

    if (elapsed() >= 2.0) {
      finish(false, "timed out waiting for version/system/motion feedback");
    } else if (elapsed() >= next_version_request_s_) {
      if (!send_checked(robot_.request_version(), "request version")) {return;}
      next_version_request_s_ += 0.40;
    }
  }

  void verify_final_state(const StateSnapshot & snapshot)
  {
    const bool stopped = snapshot.motion &&
      std::abs(snapshot.motion->linear_velocity_mps) <= 0.01 &&
      std::abs(snapshot.motion->angular_velocity_radps) <= 0.01;
    if (stopped) {
      const bool moved = max_linear_feedback_mps_ >= 0.005 &&
        max_angular_feedback_radps_ >= 0.005;
      RCLCPP_INFO(
        get_logger(),
        "max feedback: linear %.3f m/s, angular %.3f rad/s",
        max_linear_feedback_mps_, max_angular_feedback_radps_);
      finish(
        moved, moved ? "motion test passed" :
        "commanded motion was not observed in feedback");
    } else if (elapsed() >= 1.50) {
      finish(false, "robot did not confirm stopped state");
    }
  }

  bool send_motion(const MotionCommand & command)
  {
    return send_checked(robot_.set_motion(command), "send motion command");
  }

  bool send_checked(const std::error_code & error, const char * operation)
  {
    if (!error) {return true;}
    finish(false, std::string(operation) + " failed: " + error.message());
    return false;
  }

  void enter(Phase phase, const char * description)
  {
    phase_ = phase;
    phase_started_at_ = std::chrono::steady_clock::now();
    RCLCPP_INFO(get_logger(), "%s", description);
  }

  [[nodiscard]] double elapsed() const noexcept
  {
    return std::chrono::duration<double>(
      std::chrono::steady_clock::now() -
      phase_started_at_)
           .count();
  }

  void make_safe() noexcept
  {
    if (!robot_.is_connected()) {return;}
    for (int attempt = 0; attempt < 3; ++attempt) {
      static_cast<void>(robot_.stop());
    }
    robot_.disconnect();
  }

  void finish(bool passed, const std::string & message)
  {
    if (phase_ == Phase::complete) {return;}
    passed_ = passed;
    phase_ = Phase::complete;
    if (timer_) {timer_->cancel();}
    make_safe();
    if (passed) {
      RCLCPP_INFO(get_logger(), "%s", message.c_str());
    } else {
      RCLCPP_ERROR(get_logger(), "%s", message.c_str());
    }
    rclcpp::shutdown();
  }

  ScoutMini robot_;
  rclcpp::TimerBase::SharedPtr timer_;
  std::string can_interface_;
  bool run_motion_test_{false};
  double linear_velocity_mps_{0.05};
  double angular_velocity_radps_{0.10};
  double segment_duration_s_{0.60};
  double next_version_request_s_{0.40};
  double max_linear_feedback_mps_{0.0};
  double max_angular_feedback_radps_{0.0};
  Phase phase_{Phase::wait_for_feedback};
  std::chrono::steady_clock::time_point phase_started_at_{};
  bool passed_{false};
};

}  // namespace
}  // namespace scout_base

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<scout_base::ScoutMiniSmokeNode>();
  rclcpp::spin(node);
  return node->passed() ? 0 : 2;
}
