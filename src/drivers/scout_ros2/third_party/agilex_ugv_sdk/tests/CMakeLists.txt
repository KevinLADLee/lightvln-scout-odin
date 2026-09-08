add_library(agilex_ugv_sdk_test_support INTERFACE)
target_include_directories(agilex_ugv_sdk_test_support INTERFACE
  ${CMAKE_CURRENT_SOURCE_DIR}
)
target_link_libraries(agilex_ugv_sdk_test_support INTERFACE
  agilex_ugv_sdk::agilex_ugv_sdk
)

add_subdirectory(core)
add_subdirectory(models)
