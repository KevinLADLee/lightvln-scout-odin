cmake_minimum_required(VERSION 3.16)
project(agilex_ugv_sdk VERSION 1.1.0 LANGUAGES CXX)

option(BUILD_TESTING "Build agilex_ugv_sdk tests" ON)
option(BUILD_EXAMPLES "Build agilex_ugv_sdk examples" OFF)

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
find_package(Threads REQUIRED)

add_library(agilex_ugv_sdk)
add_library(agilex_ugv_sdk::agilex_ugv_sdk ALIAS agilex_ugv_sdk)
add_subdirectory(src)

target_compile_features(agilex_ugv_sdk PUBLIC cxx_std_17)
target_link_libraries(agilex_ugv_sdk PUBLIC Threads::Threads)
target_compile_options(agilex_ugv_sdk PRIVATE
  $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wshadow>
)
target_include_directories(agilex_ugv_sdk PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
set_target_properties(agilex_ugv_sdk PROPERTIES
  CXX_EXTENSIONS OFF
  EXPORT_NAME agilex_ugv_sdk
  VERSION ${PROJECT_VERSION}
  SOVERSION ${PROJECT_VERSION_MAJOR}
)

install(TARGETS agilex_ugv_sdk
  EXPORT agilex_ugv_sdkTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
  INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)
install(DIRECTORY include/agilex_ugv_sdk
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)
install(DIRECTORY docs/reference
  DESTINATION ${CMAKE_INSTALL_DATADIR}/${PROJECT_NAME}/docs
)
install(FILES LICENSE README.md CHANGELOG.md package.xml
  DESTINATION ${CMAKE_INSTALL_DATADIR}/${PROJECT_NAME}
)
install(EXPORT agilex_ugv_sdkTargets
  FILE agilex_ugv_sdkTargets.cmake
  NAMESPACE agilex_ugv_sdk::
  DESTINATION ${CMAKE_INSTALL_DATADIR}/agilex_ugv_sdk/cmake
)

configure_package_config_file(
  cmake/agilex_ugv_sdkConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/agilex_ugv_sdkConfig.cmake
  INSTALL_DESTINATION ${CMAKE_INSTALL_DATADIR}/agilex_ugv_sdk/cmake
)
write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/agilex_ugv_sdkConfigVersion.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion
)
install(FILES
  ${CMAKE_CURRENT_BINARY_DIR}/agilex_ugv_sdkConfig.cmake
  ${CMAKE_CURRENT_BINARY_DIR}/agilex_ugv_sdkConfigVersion.cmake
  DESTINATION ${CMAKE_INSTALL_DATADIR}/agilex_ugv_sdk/cmake
)

if(BUILD_EXAMPLES)
  add_subdirectory(examples)
endif()

if(BUILD_TESTING)
  include(CTest)
  add_subdirectory(tests)
endif()
