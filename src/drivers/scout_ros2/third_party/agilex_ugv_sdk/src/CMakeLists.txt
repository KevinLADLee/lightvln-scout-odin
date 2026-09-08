target_sources(agilex_ugv_sdk PRIVATE
  core/error.cpp
  core/robot.cpp
  transport/socketcan_transport.cpp
)

add_subdirectory(models)
