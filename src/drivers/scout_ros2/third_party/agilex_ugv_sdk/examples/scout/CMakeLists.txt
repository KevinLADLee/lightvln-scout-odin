add_executable(scout_mini_state scout_mini_state.cpp)
target_link_libraries(scout_mini_state PRIVATE agilex_ugv_sdk::agilex_ugv_sdk)
set_target_properties(scout_mini_state PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}"
)
