// Copyright 2026 AgileX Robotics
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>

#include "agilex_ugv_sdk/models/scout/scout_mini.hpp"
#include "geometry_msgs/msg/transform_stamped.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"
#include "scout_msgs/msg/scout_light_cmd.hpp"
#include "scout_msgs/msg/scout_rc_state.hpp"
#include "scout_msgs/msg/scout_status.hpp"
#include "tf2/LinearMath/Quaternion.h"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include "tf2_ros/transform_broadcaster.hpp"

namespace scout_base
{

class ScoutMiniNode final : public rclcpp::Node
{
public:
  ScoutMiniNode()
  : Node("scout_base"),
    port_name_(declare_parameter<std::string>("port_name", "can0")),
    odom_frame_(declare_parameter<std::string>("odom_frame", "odom")),
    base_frame_(declare_parameter<std::string>("base_frame", "base_link")),
    odom_topic_name_(
      declare_parameter<std::string>("odom_topic_name", "odom")),
    is_omni_(declare_parameter<bool>("is_omni_wheel", false)),
    robot_(is_omni_ ? agilex::ugv::ScoutMiniVariant::omni :
      agilex::ugv::ScoutMiniVariant::skid_steer)
  {
    const bool is_scout_mini =
      declare_parameter<bool>("is_scout_mini", true);
    const bool simulated_robot =
      declare_parameter<bool>("simulated_robot", false);
    const int control_rate = declare_parameter<int>("control_rate", 50);
    command_timeout_s_ = declare_parameter<double>("cmd_vel_timeout", 0.5);

    if (!is_scout_mini) {
      throw std::invalid_argument(
              "agilex_ugv_sdk currently supports the SCOUT MINI profile only");
    }
    if (simulated_robot) {
      throw std::invalid_argument(
              "simulation mode is not part of the hardware SDK wrapper");
    }
    if (control_rate < 1 || command_timeout_s_ <= 0.0) {
      throw std::invalid_argument("control_rate and cmd_vel_timeout must be positive");
    }

    if (const auto error = robot_.connect(port_name_)) {
      throw std::runtime_error(
              "failed to open CAN transport: " +
              error.message());
    }
    if (const auto error =
      robot_.set_control_mode(agilex::ugv::ControlMode::can))
    {
      throw std::runtime_error(
              "failed to enable CAN control: " +
              error.message());
    }
    odometry_publisher_ =
      create_publisher<nav_msgs::msg::Odometry>(odom_topic_name_, 50);
    status_publisher_ = create_publisher<scout_msgs::msg::ScoutStatus>(
      "scout_status", 10);
    remote_publisher_ = create_publisher<scout_msgs::msg::ScoutRCState>(
      "rc_status", 10);
    transform_broadcaster_ =
      std::make_unique<tf2_ros::TransformBroadcaster>(*this);

    motion_subscription_ = create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel", 5,
      [this](geometry_msgs::msg::Twist::ConstSharedPtr message) {
        handle_motion_command(*message);
      });
    light_subscription_ =
      create_subscription<scout_msgs::msg::ScoutLightCmd>(
      "light_control", 5,
      [this](scout_msgs::msg::ScoutLightCmd::ConstSharedPtr message) {
        handle_light_command(*message);
      });

    const auto period = std::chrono::microseconds{1'000'000 / control_rate};
    control_timer_ = create_wall_timer(period, [this] {control_cycle();});
    last_update_time_ = now();

    if (const auto error = robot_.request_version()) {
      RCLCPP_WARN(
        get_logger(), "Version request failed: %s",
        error.message().c_str());
    }

    RCLCPP_INFO(
      get_logger(), "SCOUT MINI%s profile ready in CAN commanded mode",
      is_omni_ ? " OMNI" : "");
  }

  ~ScoutMiniNode() override
  {
    for (int index = 0; index < 5; ++index) {
      static_cast<void>(robot_.stop());
      std::this_thread::sleep_for(std::chrono::milliseconds{20});
    }
  }

private:
  void handle_motion_command(const geometry_msgs::msg::Twist & message)
  {
    std::lock_guard<std::mutex> lock(command_mutex_);
    latest_command_.linear_velocity_mps = message.linear.x;
    latest_command_.angular_velocity_radps = message.angular.z;
    latest_command_.lateral_velocity_mps = is_omni_ ? message.linear.y : 0.0;
    last_command_time_ = now();
    has_command_ = true;
  }

  void handle_light_command(const scout_msgs::msg::ScoutLightCmd & message)
  {
    if (message.front_mode > 3U || message.rear_mode > 3U) {
      RCLCPP_WARN(get_logger(), "Rejected invalid light mode");
      return;
    }

    agilex::ugv::LightCommand command;
    command.enabled = message.cmd_ctrl_allowed;
    command.front_mode =
      static_cast<agilex::ugv::LightMode>(message.front_mode);
    command.front_value = message.front_custom_value;
    command.rear_mode =
      static_cast<agilex::ugv::LightMode>(message.rear_mode);
    command.rear_value = message.rear_custom_value;
    if (const auto error = robot_.set_lights(command)) {
      RCLCPP_WARN(
        get_logger(), "Light command rejected: %s",
        error.message().c_str());
    }
  }

  void control_cycle()
  {
    agilex::ugv::MotionCommand command;
    {
      std::lock_guard<std::mutex> lock(command_mutex_);
      if (has_command_ &&
        (now() - last_command_time_).seconds() <= command_timeout_s_)
      {
        command = latest_command_;
      }
    }
    if (const auto error = robot_.set_motion(command)) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 1000,
        "Motion command rejected: %s",
        error.message().c_str());
    }
    publish_state();
  }

  void publish_state()
  {
    const auto current_time = now();
    const double dt = std::max(0.0, (current_time - last_update_time_).seconds());
    last_update_time_ = current_time;
    const auto state = robot_.state();

    scout_msgs::msg::ScoutStatus status;
    status.header.stamp = current_time;
    scout_msgs::msg::ScoutRCState remote;

    if (state.motion) {
      status.linear_velocity = state.motion->linear_velocity_mps;
      status.angular_velocity = state.motion->angular_velocity_radps;
      publish_odometry(*state.motion, dt, current_time);
    }
    if (state.system) {
      status.vehicle_state =
        static_cast<std::uint8_t>(state.system->vehicle_state);
      status.control_mode =
        static_cast<std::uint8_t>(state.system->control_mode);
      status.error_code = state.system->error_flags;
      status.battery_voltage = state.system->battery_voltage_v;
    }
    if (state.lights) {
      status.light_control_enabled = state.lights->enabled;
      status.front_light_state.mode =
        static_cast<std::uint8_t>(state.lights->front_mode);
      status.front_light_state.custom_value = state.lights->front_value;
      status.rear_light_state.mode =
        static_cast<std::uint8_t>(state.lights->rear_mode);
      status.rear_light_state.custom_value = state.lights->rear_value;
    }
    if (state.remote_control) {
      remote.swa = state.remote_control->swa;
      remote.swb = state.remote_control->swb;
      remote.swc = state.remote_control->swc;
      remote.swd = state.remote_control->swd;
      remote.stick_right_h = state.remote_control->right_horizontal;
      remote.stick_right_v = state.remote_control->right_vertical;
      remote.stick_left_h = state.remote_control->left_horizontal;
      remote.stick_left_v = state.remote_control->left_vertical;
      remote.var_a = state.remote_control->knob;
    }

    constexpr std::array<std::size_t, 4> kRosIndexForMotor{0, 1, 3, 2};
    for (std::size_t motor = 0; motor < kRosIndexForMotor.size(); ++motor) {
      const auto ros_index = kRosIndexForMotor[motor];
      if (state.actuators_high_speed[motor]) {
        status.actuator_states[ros_index].rpm =
          state.actuators_high_speed[motor]->speed_rpm;
        status.actuator_states[ros_index].current =
          state.actuators_high_speed[motor]->current_a;
      }
      if (state.actuators_low_speed[motor]) {
        status.actuator_states[ros_index].driver_voltage =
          state.actuators_low_speed[motor]->driver_voltage_v;
        status.actuator_states[ros_index].driver_temperature =
          state.actuators_low_speed[motor]->driver_temperature_c;
        status.actuator_states[ros_index].motor_temperature =
          state.actuators_low_speed[motor]->motor_temperature_c;
      }
    }

    status_publisher_->publish(status);
    remote_publisher_->publish(remote);
  }

  void publish_odometry(
    const agilex::ugv::MotionState & motion, double dt,
    const rclcpp::Time & stamp)
  {
    const double lateral = is_omni_ ? motion.lateral_velocity_mps : 0.0;
    position_x_ += (motion.linear_velocity_mps * std::cos(heading_) -
      lateral * std::sin(heading_)) *
      dt;
    position_y_ += (motion.linear_velocity_mps * std::sin(heading_) +
      lateral * std::cos(heading_)) *
      dt;
    heading_ += motion.angular_velocity_radps * dt;

    tf2::Quaternion rotation;
    rotation.setRPY(0.0, 0.0, heading_);
    const auto orientation = tf2::toMsg(rotation);

    geometry_msgs::msg::TransformStamped transform;
    transform.header.stamp = stamp;
    transform.header.frame_id = odom_frame_;
    transform.child_frame_id = base_frame_;
    transform.transform.translation.x = position_x_;
    transform.transform.translation.y = position_y_;
    transform.transform.rotation = orientation;
    transform_broadcaster_->sendTransform(transform);

    nav_msgs::msg::Odometry odometry;
    odometry.header.stamp = stamp;
    odometry.header.frame_id = odom_frame_;
    odometry.child_frame_id = base_frame_;
    odometry.pose.pose.position.x = position_x_;
    odometry.pose.pose.position.y = position_y_;
    odometry.pose.pose.orientation = orientation;
    odometry.twist.twist.linear.x = motion.linear_velocity_mps;
    odometry.twist.twist.linear.y = lateral;
    odometry.twist.twist.angular.z = motion.angular_velocity_radps;
    odometry_publisher_->publish(odometry);
  }

  const std::string port_name_;
  const std::string odom_frame_;
  const std::string base_frame_;
  const std::string odom_topic_name_;
  const bool is_omni_;
  agilex::ugv::ScoutMini robot_;
  double command_timeout_s_{0.5};

  std::mutex command_mutex_;
  agilex::ugv::MotionCommand latest_command_;
  rclcpp::Time last_command_time_{0, 0, RCL_ROS_TIME};
  bool has_command_{false};
  rclcpp::Time last_update_time_{0, 0, RCL_ROS_TIME};
  double position_x_{0.0};
  double position_y_{0.0};
  double heading_{0.0};

  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odometry_publisher_;
  rclcpp::Publisher<scout_msgs::msg::ScoutStatus>::SharedPtr status_publisher_;
  rclcpp::Publisher<scout_msgs::msg::ScoutRCState>::SharedPtr remote_publisher_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr
    motion_subscription_;
  rclcpp::Subscription<scout_msgs::msg::ScoutLightCmd>::SharedPtr
    light_subscription_;
  rclcpp::TimerBase::SharedPtr control_timer_;
  std::unique_ptr<tf2_ros::TransformBroadcaster> transform_broadcaster_;
};

}  // namespace scout_base

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<scout_base::ScoutMiniNode>());
  } catch (const std::exception & exception) {
    RCLCPP_FATAL(rclcpp::get_logger("scout_base"), "%s", exception.what());
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
  return 0;
}
