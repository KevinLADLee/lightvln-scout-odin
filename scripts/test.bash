#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
LIGHTNAV_SRC="${WORKSPACE_ROOT}/src/lightnav"
INTEGRATION_SRC="${WORKSPACE_ROOT}/src/integration"
PYTHON_BIN="${WORKSPACE_ROOT}/.venv/bin/python"
ROS_DISTRO_NAME="${ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO_NAME}/setup.bash"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing ${PYTHON_BIN}; run scripts/bootstrap.bash first." >&2
  exit 1
fi
if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "ROS 2 setup not found: ${ROS_SETUP}" >&2
  exit 1
fi
# shellcheck disable=SC1090
set +u
source "${ROS_SETUP}"
if [[ -f "${WORKSPACE_ROOT}/install/setup.bash" ]]; then
  source "${WORKSPACE_ROOT}/install/setup.bash"
fi
set -u
cd "${WORKSPACE_ROOT}"
# Tests construct ROS publishers. Default to a localhost-only test domain;
# callers may choose another unused domain explicitly.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-199}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-1}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-${WORKSPACE_ROOT}/log/test-ros}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${WORKSPACE_ROOT}/.matplotlib}"
"${PYTHON_BIN}" -c 'from scout_msgs.msg import ScoutStatus' || {
  echo "Build this checkout first with scripts/build.bash to generate scout_msgs." >&2
  exit 1
}
"${PYTHON_BIN}" "${WORKSPACE_ROOT}/scripts/check_repository.py"
export PYTHONPATH="${INTEGRATION_SRC}/lightvln_scout:${LIGHTNAV_SRC}/vln_client:${LIGHTNAV_SRC}/vln_web:${LIGHTNAV_SRC}/vln_mpc${PYTHONPATH:+:${PYTHONPATH}}"
"${PYTHON_BIN}" -m ruff check --config "${WORKSPACE_ROOT}/ruff.toml" \
  "${INTEGRATION_SRC}/lightvln_scout/launch" \
  "${INTEGRATION_SRC}/lightvln_scout/lightvln_scout" \
  "${INTEGRATION_SRC}/lightvln_scout/test" \
  "${LIGHTNAV_SRC}/vln_client/vln_client" \
  "${LIGHTNAV_SRC}/vln_client/test" \
  "${LIGHTNAV_SRC}/vln_web/vln_web" \
  "${LIGHTNAV_SRC}/vln_web/test" \
  "${WORKSPACE_ROOT}/scripts" \
  "${WORKSPACE_ROOT}/tests"
"${PYTHON_BIN}" -m ruff check --select E,F \
  "${LIGHTNAV_SRC}/vln_mpc/vln_mpc" \
  "${LIGHTNAV_SRC}/vln_mpc/test"
"${PYTHON_BIN}" -m pytest -q --import-mode=importlib \
  "${INTEGRATION_SRC}/lightvln_scout/test" \
  "${LIGHTNAV_SRC}/vln_client/test" \
  "${LIGHTNAV_SRC}/vln_web/test" \
  "${LIGHTNAV_SRC}/vln_mpc/test" \
  "${WORKSPACE_ROOT}/tests" \
  "$@"
