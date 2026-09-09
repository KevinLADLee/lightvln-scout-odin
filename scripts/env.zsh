#!/usr/bin/env zsh

if [[ -z "${ZSH_EVAL_CONTEXT:-}" || "${ZSH_EVAL_CONTEXT}" != *:file ]]; then
  print -u2 "Source this file instead: source scripts/env.zsh"
  exit 2
fi

_LIGHTNAV_ENV_FILE="${(%):-%N}"
_LIGHTNAV_SCRIPT_DIR="${_LIGHTNAV_ENV_FILE:A:h}"
_LIGHTNAV_WORKSPACE_ROOT="${_LIGHTNAV_SCRIPT_DIR:h}"
_LIGHTNAV_ROS_DISTRO="${ROS_DISTRO:-humble}"

for _LIGHTNAV_REQUIRED in "/opt/ros/${_LIGHTNAV_ROS_DISTRO}/setup.zsh" \
  "${_LIGHTNAV_WORKSPACE_ROOT}/.venv/bin/activate"; do
  if [[ ! -f "${_LIGHTNAV_REQUIRED}" ]]; then
    print -u2 "Missing ${_LIGHTNAV_REQUIRED}; install ROS and run scripts/bootstrap.bash."
    unset _LIGHTNAV_REQUIRED _LIGHTNAV_ENV_FILE _LIGHTNAV_SCRIPT_DIR
    unset _LIGHTNAV_WORKSPACE_ROOT _LIGHTNAV_ROS_DISTRO
    return 1
  fi
done
unset _LIGHTNAV_REQUIRED

source "/opt/ros/${_LIGHTNAV_ROS_DISTRO}/setup.zsh" || return 1
source "${_LIGHTNAV_WORKSPACE_ROOT}/.venv/bin/activate" || return 1
if [[ -f "${_LIGHTNAV_WORKSPACE_ROOT}/install/setup.zsh" ]]; then
  source "${_LIGHTNAV_WORKSPACE_ROOT}/install/setup.zsh" || return 1
fi

export ROS_LOG_DIR="${ROS_LOG_DIR:-${_LIGHTNAV_WORKSPACE_ROOT}/log/ros}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${_LIGHTNAV_WORKSPACE_ROOT}/.matplotlib}"
export LIGHTVLN_SCOUT_WS="${_LIGHTNAV_WORKSPACE_ROOT}"
mkdir -p "${ROS_LOG_DIR}" "${MPLCONFIGDIR}"
print "LightVLN Scout environment: ROS ${_LIGHTNAV_ROS_DISTRO}, ${VIRTUAL_ENV}"

unset _LIGHTNAV_ENV_FILE _LIGHTNAV_SCRIPT_DIR _LIGHTNAV_WORKSPACE_ROOT
unset _LIGHTNAV_ROS_DISTRO
