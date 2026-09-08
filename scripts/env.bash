#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Source this file instead: source scripts/env.bash" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO_NAME="${ROS_DISTRO:-humble}"

# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
# shellcheck disable=SC1091
source "${WORKSPACE_ROOT}/.venv/bin/activate"
if [[ -f "${WORKSPACE_ROOT}/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "${WORKSPACE_ROOT}/install/setup.bash"
fi

export ROS_LOG_DIR="${ROS_LOG_DIR:-${WORKSPACE_ROOT}/log/ros}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${WORKSPACE_ROOT}/.matplotlib}"
export LIGHTVLN_SCOUT_WS="${WORKSPACE_ROOT}"
mkdir -p "${ROS_LOG_DIR}" "${MPLCONFIGDIR}"
echo "LightVLN Scout environment: ROS ${ROS_DISTRO_NAME}, ${VIRTUAL_ENV}"
unset SCRIPT_DIR WORKSPACE_ROOT ROS_DISTRO_NAME
