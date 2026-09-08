#!/usr/bin/env bash
set -euo pipefail

SCOUT_URDF_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ros2 run xacro xacro "${SCOUT_URDF_DIR}/scout_v2.xacro" \
  -o "${SCOUT_URDF_DIR}/scout_v2.urdf"
