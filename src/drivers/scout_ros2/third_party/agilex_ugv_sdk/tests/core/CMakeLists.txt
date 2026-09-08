add_executable(test_robot test_robot.cpp)
target_link_libraries(test_robot PRIVATE agilex_ugv_sdk_test_support)
add_test(NAME robot_core COMMAND test_robot)
