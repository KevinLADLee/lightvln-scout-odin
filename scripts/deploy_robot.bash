#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_HOST="${LIGHTNAV_DEPLOY_HOST:-}"
DEPLOY_ROOT="${LIGHTNAV_DEPLOY_ROOT:-lightvln-scout-odin}"
ASK_PASSWORD=0
SSH_PREFIX=()
RSYNC_SSH="ssh -o StrictHostKeyChecking=accept-new"

usage() {
  cat <<'USAGE'
Usage: LIGHTNAV_DEPLOY_HOST=user@robot-host ./scripts/deploy_robot.bash [--ask-password]

LIGHTNAV_DEPLOY_HOST  Required SSH hostname or alias, optionally prefixed by user@.
                     Use an SSH alias for IPv6 addresses or custom ports.
LIGHTNAV_DEPLOY_ROOT  Remote directory; default: lightvln-scout-odin under remote home.
                     Absolute paths are supported. Use letters, digits, _, -, ., /;
                     spaces, shell expressions, dot components, and empty components
                     are rejected. Do not use a symlink as the remote destination.

Copies source with rsync; does not build, restart services, or delete remote files.
Preserves safe relative symlinks; never copies a symlink target's contents.
--ask-password       Prompt for an SSH password using sshpass.
-h, --help           Show this help without making a connection.
USAGE
}

for arg in "$@"; do
  case "${arg}" in
    --ask-password) ASK_PASSWORD=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

if [[ -z "${DEPLOY_HOST}" ]]; then
  echo "Set LIGHTNAV_DEPLOY_HOST to your intended SSH destination." >&2
  usage >&2
  exit 2
fi
if [[ ! "${DEPLOY_HOST}" =~ ^([[:alnum:]_][[:alnum:]_.-]*@)?[[:alnum:]_][[:alnum:]_.-]*$ ]]; then
  echo "Invalid LIGHTNAV_DEPLOY_HOST; use an SSH hostname or alias." >&2
  exit 2
fi
if [[ ! "${DEPLOY_ROOT}" =~ ^/?[[:alnum:]_.][[:alnum:]_.-]*(/[[:alnum:]_.][[:alnum:]_.-]*)*$ \
   || "/${DEPLOY_ROOT}/" == */./* || "/${DEPLOY_ROOT}/" == */../* ]]; then
  echo "Invalid LIGHTNAV_DEPLOY_ROOT; supply a dedicated workspace directory." >&2
  exit 2
fi

if (( ASK_PASSWORD )); then
  if ! command -v sshpass >/dev/null 2>&1; then
    echo "sshpass is required for --ask-password." >&2
    exit 1
  fi
  read -r -s -p "Password for ${DEPLOY_HOST}: " SSHPASS
  echo
  export SSHPASS
  SSH_PREFIX=(sshpass -e)
  RSYNC_SSH="sshpass -e ssh -o StrictHostKeyChecking=accept-new"
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on the development and robot computers." >&2
  exit 1
fi
"${SSH_PREFIX[@]}" ssh -o StrictHostKeyChecking=accept-new \
  "${DEPLOY_HOST}" "mkdir -p -- '${DEPLOY_ROOT}'"
rsync -az --safe-links --protect-args \
  --exclude=.git/ \
  --exclude=.claude/ \
  --exclude=.codex/ \
  --exclude=.agents/ \
  --exclude=.gitnexus/ \
  --exclude=AGENTS.md \
  --exclude=CLAUDE.md \
  --exclude=.local/ \
  --exclude=.backups/ \
  --exclude=.env \
  --exclude='.env.*' \
  --exclude=.venv/ \
  --exclude=.uv-cache/ \
  --exclude=.matplotlib/ \
  --exclude=.ruff_cache/ \
  --exclude=build/ \
  --exclude=install/ \
  --exclude=log/ \
  --exclude=__pycache__/ \
  --exclude=.pytest_cache/ \
  --exclude=image/ \
  --exclude=src/odin_ros_driver/ \
  -e "${RSYNC_SSH}" \
  "${WORKSPACE_ROOT}/" \
  "${DEPLOY_HOST}:${DEPLOY_ROOT}/"

echo "Source deployed to ${DEPLOY_HOST}:${DEPLOY_ROOT}"
echo "On the target, install the prerequisites and run:"
echo "  cd '${DEPLOY_ROOT}'"
echo "  ./scripts/bootstrap.bash --rosdep"
