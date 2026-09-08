cmake_minimum_required(VERSION 3.16)
project(scout_base)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

find_package(scout_msgs REQUIRED)
find_package(agilex_ugv_sdk 1.1 REQUIRED)

add_executable(scout_base_node
  src/scout_mini_node.cpp)
target_link_libraries(scout_base_node agilex_ugv_sdk::agilex_ugv_sdk)
ament_target_dependencies(scout_base_node
  geometry_msgs
  nav_msgs
  rclcpp
  scout_msgs
  sensor_msgs
  std_msgs
  tf2
  tf2_geometry_msgs
  tf2_ros)

add_executable(scout_mini_smoke src/scout_mini_smoke.cpp)
target_link_libraries(scout_mini_smoke agilex_ugv_sdk::agilex_ugv_sdk)
ament_target_dependencies(scout_mini_smoke rclcpp)

install(TARGETS scout_base_node scout_mini_smoke
  DESTINATION lib/${PROJECT_NAME})

install(FILES launch/scout_mini.launch.py
  DESTINATION share/${PROJECT_NAME}/launch)

install(FILES README.md
  DESTINATION share/${PROJECT_NAME})

install(FILES ../LICENSE ../NOTICE
  DESTINATION share/${PROJECT_NAME})

ament_python_install_package(scout_base_tools)

install(PROGRAMS scripts/scout_test_tui
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_copyright REQUIRED)
  find_package(ament_cmake_cpplint REQUIRED)
  find_package(ament_cmake_flake8 REQUIRED)
  find_package(ament_cmake_lint_cmake REQUIRED)
  find_package(ament_cmake_pep257 REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  find_package(ament_cmake_uncrustify REQUIRED)

  ament_copyright(
    src/scout_mini_node.cpp
    launch/scout_mini.launch.py
    scout_base_tools/__init__.py
    scout_base_tools/app.py
    scout_base_tools/core.py
    scripts/scout_test_tui
    test/test_tui_core.py)
  ament_cpplint(src/scout_mini_node.cpp)
  ament_flake8(
    launch/scout_mini.launch.py
    scout_base_tools
    scripts/scout_test_tui
    test/test_tui_core.py)
  ament_lint_cmake(CMakeLists.txt)
  ament_pep257(
    launch/scout_mini.launch.py
    scout_base_tools
    scripts/scout_test_tui
    test/test_tui_core.py)
  ament_add_pytest_test(test_tui_core test/test_tui_core.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR})
  ament_uncrustify(src/scout_mini_node.cpp src/scout_mini_smoke.cpp)
endif()

ament_package()
