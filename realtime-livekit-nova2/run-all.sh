#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="${ROOT_DIR}/ui"

if [[ ! -d "${UI_DIR}" ]]; then
  echo "Error: UI directory not found at ${UI_DIR}"
  exit 1
fi

for cmd in uv npm livekit-server; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Error: ${cmd} is not installed or not on PATH."
    exit 1
  fi
done

FORCE_PROMPT="false"
while getopts ":p" opt; do
  case "${opt}" in
    p) FORCE_PROMPT="true" ;;
    *)
      echo "Usage: $0 [-p]"
      exit 1
      ;;
  esac
done
shift $((OPTIND - 1))

is_port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :${port} )" | awk 'NR>1 {found=1} END {exit !found}'
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN -t >/dev/null 2>&1
    return
  fi
  return 1
}

prompt_required() {
  local var_name="$1"
  local secret="${2:-false}"
  local value=""

  while [[ -z "${value}" ]]; do
    if [[ "${secret}" == "true" ]]; then
      read -rsp "${var_name}: " value
      echo
    else
      read -rp "${var_name}: " value
    fi
  done

  export "${var_name}=${value}"
}

PROMPT_AWS="${PROMPT_AWS:-true}"
if [[ "${PROMPT_AWS}" == "true" ]]; then
  if [[ "${FORCE_PROMPT}" == "true" || -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" || -z "${AWS_SESSION_TOKEN:-}" ]]; then
    echo "Enter temporary AWS credentials for this session."
  fi
  if [[ "${FORCE_PROMPT}" == "true" || -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
    prompt_required "AWS_ACCESS_KEY_ID"
  fi
  if [[ "${FORCE_PROMPT}" == "true" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
    prompt_required "AWS_SECRET_ACCESS_KEY" "true"
  fi
  if [[ "${FORCE_PROMPT}" == "true" || -z "${AWS_SESSION_TOKEN:-}" ]]; then
    prompt_required "AWS_SESSION_TOKEN" "true"
  fi

  if [[ "${FORCE_PROMPT}" == "true" || ( -z "${AWS_REGION:-}" && -z "${AWS_DEFAULT_REGION:-}" ) ]]; then
    read -rp "AWS_REGION [${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}]: " region
    region="${region:-${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}}"
    export AWS_REGION="${region}"
    export AWS_DEFAULT_REGION="${region}"
  elif [[ -n "${AWS_REGION:-}" && -z "${AWS_DEFAULT_REGION:-}" ]]; then
    export AWS_DEFAULT_REGION="${AWS_REGION}"
  elif [[ -z "${AWS_REGION:-}" && -n "${AWS_DEFAULT_REGION:-}" ]]; then
    export AWS_REGION="${AWS_DEFAULT_REGION}"
  fi
else
  : "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID must be set when PROMPT_AWS=false}"
  : "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY must be set when PROMPT_AWS=false}"
  : "${AWS_SESSION_TOKEN:?AWS_SESSION_TOKEN must be set when PROMPT_AWS=false}"
  if [[ -z "${AWS_REGION:-}" && -z "${AWS_DEFAULT_REGION:-}" ]]; then
    export AWS_REGION="us-east-1"
    export AWS_DEFAULT_REGION="us-east-1"
  fi
fi

AGENT_MODE="${AGENT_MODE:-connect}"
if [[ "${AGENT_MODE}" != "start" && "${AGENT_MODE}" != "dev" && "${AGENT_MODE}" != "connect" ]]; then
  echo "Error: AGENT_MODE must be one of: start, dev, connect"
  exit 1
fi

LIVEKIT_ROOM="${LIVEKIT_ROOM:-my-first-room}"
PROMPT_LIVEKIT_ROOM="${PROMPT_LIVEKIT_ROOM:-true}"
if [[ "${AGENT_MODE}" == "connect" && "${PROMPT_LIVEKIT_ROOM}" == "true" ]]; then
  read -rp "LIVEKIT room [${LIVEKIT_ROOM}]: " input_room
  if [[ -n "${input_room}" ]]; then
    LIVEKIT_ROOM="${input_room}"
  fi
fi

AGENT_SCRIPT="${AGENT_SCRIPT:-agent.py}"
if [[ ! -f "${ROOT_DIR}/${AGENT_SCRIPT}" ]]; then
  echo "Error: agent script not found: ${ROOT_DIR}/${AGENT_SCRIPT}"
  exit 1
fi

AGENT_PID=""
LIVEKIT_PID=""
STARTED_LIVEKIT_SERVER="false"
cleanup() {
  echo
  echo "Stopping services..."
  if [[ -n "${AGENT_PID}" ]] && kill -0 "${AGENT_PID}" 2>/dev/null; then
    kill "${AGENT_PID}" 2>/dev/null || true
    wait "${AGENT_PID}" 2>/dev/null || true
  fi
  if [[ "${STARTED_LIVEKIT_SERVER}" == "true" ]] && [[ -n "${LIVEKIT_PID}" ]] && kill -0 "${LIVEKIT_PID}" 2>/dev/null; then
    kill "${LIVEKIT_PID}" 2>/dev/null || true
    wait "${LIVEKIT_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

PREFERRED_UI_PORT="${UI_PORT:-3002}"
STRICT_UI_PORT="${STRICT_UI_PORT:-false}"
UI_PORT="${PREFERRED_UI_PORT}"
if is_port_in_use "${UI_PORT}"; then
  if [[ "${STRICT_UI_PORT}" == "true" ]]; then
    echo "Error: UI port ${UI_PORT} is already in use."
    exit 1
  fi
  for _ in {1..20}; do
    UI_PORT=$((UI_PORT + 1))
    if ! is_port_in_use "${UI_PORT}"; then
      break
    fi
  done
  if is_port_in_use "${UI_PORT}"; then
    echo "Error: no free UI port found near ${PREFERRED_UI_PORT}."
    exit 1
  fi
  echo "Port ${PREFERRED_UI_PORT} is busy. Using http://localhost:${UI_PORT} instead."
fi
export PORT="${UI_PORT}"
export CI=true
export LIVEKIT_AGENT_PORT="${LIVEKIT_AGENT_PORT:-0}"

if pgrep -f "livekit-server --dev" >/dev/null 2>&1; then
  echo "Detected existing livekit-server --dev process. Reusing it."
else
  echo "Starting livekit-server --dev ..."
  (
    cd "${ROOT_DIR}"
    livekit-server --dev
  ) &
  LIVEKIT_PID=$!
  STARTED_LIVEKIT_SERVER="true"
fi

if [[ "${AGENT_MODE}" == "connect" ]]; then
  RECONNECT_DELAY_SECONDS="${RECONNECT_DELAY_SECONDS:-1}"
  echo "Starting LiveKit agent (${AGENT_SCRIPT}) in connect mode for room '${LIVEKIT_ROOM}'..."
  (
    cd "${ROOT_DIR}"
    while true; do
      uv run python "${AGENT_SCRIPT}" connect --room "${LIVEKIT_ROOM}" || true
      echo "LiveKit connect session ended, retrying in ${RECONNECT_DELAY_SECONDS}s..."
      sleep "${RECONNECT_DELAY_SECONDS}"
    done
  ) &
elif [[ "${AGENT_MODE}" == "dev" ]]; then
  echo "Starting LiveKit agent (${AGENT_SCRIPT}) in dev mode..."
  (
    cd "${ROOT_DIR}"
    uv run python "${AGENT_SCRIPT}" dev --no-reload
  ) &
else
  echo "Starting LiveKit agent (${AGENT_SCRIPT}) in start mode..."
  (
    cd "${ROOT_DIR}"
    uv run python "${AGENT_SCRIPT}" start
  ) &
fi
AGENT_PID=$!

echo "Starting frontend on http://localhost:${UI_PORT} ..."
cd "${UI_DIR}"
npm start
