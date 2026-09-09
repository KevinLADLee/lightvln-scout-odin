#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Source this file instead: source scripts/env.bash" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO_NAME="${ROS_DISTRO:-humble}"

for _LIGHTNAV_REQUIRED in "/opt/ros/${ROS_DISTRO_NAME}/setup.bash" \
  "${WORKSPACE_ROOT}/.venv/bin/activate"; do
  if [[ ! -f "${_LIGHTNAV_REQUIRED}" ]]; then
    echo "Missing ${_LIGHTNAV_REQUIRED}; install ROS and run scripts/bootstrap.bash." >&2
    unset _LIGHTNAV_REQUIRED SCRIPT_DIR WORKSPACE_ROOT ROS_DISTRO_NAME
    return 1
  fi
done
unset _LIGHTNAV_REQUIRED

# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO_NAME}/setup.bash" || return 1
# shellcheck disable=SC1091
source "${WORKSPACE_ROOT}/.venv/bin/activate" || return 1
if [[ -f "${WORKSPACE_ROOT}/install/setup.bash" ]]; then
  # shellcheck disable=SC1091
  source "${WORKSPACE_ROOT}/install/setup.bash" || return 1
fi

export ROS_LOG_DIR="${ROS_LOG_DIR:-${WORKSPACE_ROOT}/log/ros}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${WORKSPACE_ROOT}/.matplotlib}"
export LIGHTVLN_SCOUT_WS="${WORKSPACE_ROOT}"
mkdir -p "${ROS_LOG_DIR}" "${MPLCONFIGDIR}"
echo "LightVLN Scout environment: ROS ${ROS_DISTRO_NAME}, ${VIRTUAL_ENV}"
unset SCRIPT_DIR WORKSPACE_ROOT ROS_DISTRO_NAME
