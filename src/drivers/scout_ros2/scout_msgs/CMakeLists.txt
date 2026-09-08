cmake_minimum_required(VERSION 3.8)
project(scout_msgs)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

set(message_files
  "msg/ScoutActuatorState.msg"
  "msg/ScoutLightCmd.msg"
  "msg/ScoutLightState.msg"
  "msg/ScoutRCState.msg"
  "msg/ScoutStatus.msg"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${message_files}
  DEPENDENCIES
    builtin_interfaces
    std_msgs
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)

install(FILES ../LICENSE ../NOTICE
  DESTINATION share/${PROJECT_NAME})

ament_package()
