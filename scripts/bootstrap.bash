#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO_NAME="${ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
RUN_ROSDEP=0
RUN_BUILD=1
BUILD_ARGS=()
SOURCE_PATHS=("${WORKSPACE_ROOT}/src")

for arg in "$@"; do
  case "${arg}" in
    --rosdep) RUN_ROSDEP=1 ;;
    --no-build) RUN_BUILD=0 ;;
    *) BUILD_ARGS+=("${arg}") ;;
  esac
done

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "ROS 2 setup not found: ${ROS_SETUP}" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/" >&2
  exit 1
fi
# shellcheck disable=SC1090
set +u
source "${ROS_SETUP}"
set -u
export UV_CACHE_DIR="${UV_CACHE_DIR:-${WORKSPACE_ROOT}/.uv-cache}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${WORKSPACE_ROOT}/.matplotlib}"
# Desktop notifications block on D-Bus for tens of seconds in headless SSH.
export COLCON_EXTENSION_BLOCKLIST="colcon_core.event_handler.desktop_notification${COLCON_EXTENSION_BLOCKLIST:+:${COLCON_EXTENSION_BLOCKLIST}}"
mkdir -p "${UV_CACHE_DIR}" "${MPLCONFIGDIR}"

if (( RUN_ROSDEP )); then
  rosdep install \
    --from-paths "${SOURCE_PATHS[@]}" \
    --ignore-src \
    --rosdistro "${ROS_DISTRO_NAME}" \
    -y
fi

if [[ ! -x "${WORKSPACE_ROOT}/.venv/bin/python" ]]; then
  uv venv \
    --python /usr/bin/python3 \
    --system-site-packages \
    "${WORKSPACE_ROOT}/.venv"
fi
if ! grep -q '^include-system-site-packages = true$' \
  "${WORKSPACE_ROOT}/.venv/pyvenv.cfg"; then
  echo ".venv must expose ROS system packages; recreate it with this script." >&2
  exit 1
fi

if ! "${WORKSPACE_ROOT}/.venv/bin/python" \
  "${WORKSPACE_ROOT}/scripts/check_python_env.py"; then
  # Resolve the complete Python dependency tree into the overlay. ROS binary
  # modules stay in the system site-packages; NumPy remains below version 2.
  uv pip install \
    --python "${WORKSPACE_ROOT}/.venv/bin/python" \
    --requirements "${WORKSPACE_ROOT}/requirements.txt" \
    --requirements "${WORKSPACE_ROOT}/requirements-dev.txt"

  "${WORKSPACE_ROOT}/.venv/bin/python" \
    "${WORKSPACE_ROOT}/scripts/check_python_env.py"
else
  echo "Python overlay already satisfies requirements; skipping downloads"
fi

if (( RUN_BUILD )); then
  "${WORKSPACE_ROOT}/.venv/bin/python" -m colcon \
    --log-base "${WORKSPACE_ROOT}/log" \
    build \
    --base-paths "${SOURCE_PATHS[@]}" \
    --build-base "${WORKSPACE_ROOT}/build" \
    --install-base "${WORKSPACE_ROOT}/install" \
    --symlink-install \
    "${BUILD_ARGS[@]}"
fi

echo
echo "Workspace ready. In a new shell run one of:"
echo "  source ${WORKSPACE_ROOT}/scripts/env.bash"
echo "  source ${WORKSPACE_ROOT}/scripts/env.zsh"
