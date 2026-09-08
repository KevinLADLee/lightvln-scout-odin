#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO_NAME="${ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
PYTHON_BIN="${WORKSPACE_ROOT}/.venv/bin/python"
SOURCE_PATHS=("${WORKSPACE_ROOT}/src")

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "ROS 2 setup not found: ${ROS_SETUP}" >&2
  exit 1
fi
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing ${PYTHON_BIN}; run scripts/bootstrap.bash first." >&2
  exit 1
fi
# shellcheck disable=SC1090
set +u
source "${ROS_SETUP}"
set -u
export UV_CACHE_DIR="${UV_CACHE_DIR:-${WORKSPACE_ROOT}/.uv-cache}"
export COLCON_EXTENSION_BLOCKLIST="colcon_core.event_handler.desktop_notification${COLCON_EXTENSION_BLOCKLIST:+:${COLCON_EXTENSION_BLOCKLIST}}"
"${PYTHON_BIN}" -m colcon \
  --log-base "${WORKSPACE_ROOT}/log" \
  build \
  --base-paths "${SOURCE_PATHS[@]}" \
  --build-base "${WORKSPACE_ROOT}/build" \
  --install-base "${WORKSPACE_ROOT}/install" \
  --symlink-install \
  "$@"
