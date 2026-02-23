#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT_DIR}/.logs"
HUB_DIR="${ROOT_DIR}/hub"

BEDROCK_DIR="${ROOT_DIR}/realtime-bedrock-nova2"
LIVEKIT_DIR="${ROOT_DIR}/realtime-livekit-nova2"
PIPECAT_DIR="${ROOT_DIR}/realtime-pipecat-nova2"
POC_DIR="${ROOT_DIR}/voice-ai-poc"
PIPECAT_QUICKSTART_DIR="${ROOT_DIR}/traditional-pipecat-pipeline"
AGENT_STARTER_DIR="${ROOT_DIR}/traditional-livekit-agent"
AGENT_STARTER_CONFIG_PATH="${HUB_DIR}/agent-starter-config.json"

BEDROCK_UI_PORT="${BEDROCK_UI_PORT:-3001}"
LIVEKIT_UI_PORT="${LIVEKIT_UI_PORT:-3002}"
PIPECAT_UI_PORT="${PIPECAT_UI_PORT:-5173}"
POC_UI_PORT="${POC_UI_PORT:-5174}"
PIPECAT_QUICKSTART_UI_PORT="${PIPECAT_QUICKSTART_UI_PORT:-7861}"
HUB_PORT="${HUB_PORT:-8090}"
AGENT_STARTER_ROOM="${AGENT_STARTER_ROOM:-agent-starter-room}"

LIVEKIT_ROOM="${LIVEKIT_ROOM:-my-first-room}"
AUTO_OPEN_BROWSER="${AUTO_OPEN_BROWSER:-true}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-90}"
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

for cmd in bash curl python3 lk; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Error: ${cmd} is not installed or not on PATH."
    exit 1
  fi
done

for required_dir in "${BEDROCK_DIR}" "${LIVEKIT_DIR}" "${PIPECAT_DIR}" "${POC_DIR}" "${PIPECAT_QUICKSTART_DIR}" "${AGENT_STARTER_DIR}" "${HUB_DIR}"; do
  if [[ ! -d "${required_dir}" ]]; then
    echo "Error: missing required directory: ${required_dir}"
    exit 1
  fi
done

mkdir -p "${LOG_DIR}"

build_agent_starter_client_config() {
  if [[ ! -f "${AGENT_STARTER_DIR}/.env.local" ]]; then
    echo "Error: missing ${AGENT_STARTER_DIR}/.env.local for agent starter client token generation."
    exit 1
  fi

  local server_url=""
  local api_key=""
  local api_secret=""
  local identity="web-${RANDOM}-$(date +%s)"
  local token_output=""
  local token=""

  # shellcheck disable=SC1091
  set -a && source "${AGENT_STARTER_DIR}/.env.local" && set +a
  server_url="${LIVEKIT_URL:-}"
  api_key="${LIVEKIT_API_KEY:-}"
  api_secret="${LIVEKIT_API_SECRET:-}"

  if [[ -z "${server_url}" || -z "${api_key}" || -z "${api_secret}" ]]; then
    echo "Error: LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET must be set in ${AGENT_STARTER_DIR}/.env.local."
    exit 1
  fi

  token_output="$(
    lk token create \
      --url "${server_url}" \
      --api-key "${api_key}" \
      --api-secret "${api_secret}" \
      --join \
      --room "${AGENT_STARTER_ROOM}" \
      --identity "${identity}" \
      --agent "my-agent" \
      --valid-for "1h"
  )"

  token="$(printf "%s\n" "${token_output}" | sed -n 's/^Access token: //p')"
  if [[ -z "${token}" ]]; then
    echo "Error: failed to generate agent starter client token."
    exit 1
  fi

  cat > "${AGENT_STARTER_CONFIG_PATH}" <<EOF
{
  "serverUrl": "${server_url}",
  "room": "${AGENT_STARTER_ROOM}",
  "identity": "${identity}",
  "token": "${token}"
}
EOF
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

wait_for_http() {
  local name="$1"
  local url="$2"
  local timeout="$3"

  local attempt=0
  while [[ "${attempt}" -lt "${timeout}" ]]; do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "Ready: ${name} (${url})"
      return 0
    fi
    sleep 1
    attempt=$((attempt + 1))
  done

  echo "Error: timeout waiting for ${name} (${url})"
  return 1
}

PIDS=()
cleanup() {
  echo
  echo "Stopping all demo services..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
    fi
  done
  for pid in "${PIDS[@]:-}"; do
    wait "${pid}" 2>/dev/null || true
  done
  echo "All launched services stopped."
}
trap cleanup EXIT INT TERM

if [[ "${FORCE_PROMPT}" == "true" || -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" || -z "${AWS_SESSION_TOKEN:-}" ]]; then
  echo "Enter temporary AWS credentials for all demos."
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

echo "Preparing Agent Starter client config..."
build_agent_starter_client_config

echo "Starting Bedrock demo..."
(
  cd "${BEDROCK_DIR}"
  PROMPT_AWS=false STRICT_UI_PORT=true UI_PORT="${BEDROCK_UI_PORT}" ./run-all.sh
) >"${LOG_DIR}/bedrock.log" 2>&1 &
PIDS+=($!)

echo "Starting LiveKit demo..."
(
  cd "${LIVEKIT_DIR}"
  PROMPT_AWS=false AGENT_MODE=connect PROMPT_LIVEKIT_ROOM=false LIVEKIT_ROOM="${LIVEKIT_ROOM}" STRICT_UI_PORT=true UI_PORT="${LIVEKIT_UI_PORT}" ./run-all.sh
) >"${LOG_DIR}/livekit.log" 2>&1 &
PIDS+=($!)

echo "Starting Pipecat demo..."
(
  cd "${PIPECAT_DIR}"
  PROMPT_AWS=false STRICT_UI_PORT=true ALLOW_UI_PORT_FALLBACK=false UI_PORT="${PIPECAT_UI_PORT}" ./run-all.sh
) >"${LOG_DIR}/pipecat.log" 2>&1 &
PIDS+=($!)

echo "Starting POC demo..."
(
  cd "${POC_DIR}"
  PROMPT_AWS=false STRICT_UI_PORT=true UI_PORT="${POC_UI_PORT}" ./run-all.sh
) >"${LOG_DIR}/voice-ai-poc.log" 2>&1 &
PIDS+=($!)

echo "Starting Pipecat Quickstart (traditional)..."
(
  cd "${PIPECAT_QUICKSTART_DIR}"
  uv run bot.py --host 0.0.0.0 --port "${PIPECAT_QUICKSTART_UI_PORT}"
) >"${LOG_DIR}/traditional-pipecat-pipeline.log" 2>&1 &
PIDS+=($!)

echo "Starting Agent Starter Python (traditional)..."
(
  cd "${AGENT_STARTER_DIR}"
  uv run python src/agent.py dev --no-reload
) >"${LOG_DIR}/traditional-livekit-agent.log" 2>&1 &
PIDS+=($!)

echo "Starting unified hub page on port ${HUB_PORT}..."
(
  cd "${ROOT_DIR}"
  python3 -m http.server "${HUB_PORT}" --directory "${ROOT_DIR}"
) >"${LOG_DIR}/hub.log" 2>&1 &
PIDS+=($!)

wait_for_http "Bedrock UI" "http://localhost:${BEDROCK_UI_PORT}" "${WAIT_TIMEOUT_SECONDS}"
wait_for_http "LiveKit UI" "http://localhost:${LIVEKIT_UI_PORT}" "${WAIT_TIMEOUT_SECONDS}"
wait_for_http "Pipecat UI" "http://localhost:${PIPECAT_UI_PORT}" "${WAIT_TIMEOUT_SECONDS}"
wait_for_http "POC UI" "http://localhost:${POC_UI_PORT}" "${WAIT_TIMEOUT_SECONDS}"
wait_for_http "Pipecat Quickstart UI" "http://localhost:${PIPECAT_QUICKSTART_UI_PORT}" "${WAIT_TIMEOUT_SECONDS}"
wait_for_http "Hub UI" "http://localhost:${HUB_PORT}/hub/index.html" "${WAIT_TIMEOUT_SECONDS}"

echo
echo "Unified hub is ready: http://localhost:${HUB_PORT}/hub/index.html"
echo "Bedrock: http://localhost:${BEDROCK_UI_PORT}"
echo "LiveKit: http://localhost:${LIVEKIT_UI_PORT}"
echo "Pipecat: http://localhost:${PIPECAT_UI_PORT}"
echo "Voice AI POC: http://localhost:${POC_UI_PORT}"
echo "Pipecat Quickstart: http://localhost:${PIPECAT_QUICKSTART_UI_PORT}"
echo "Agent Starter Python: running (worker mode, no local web UI)"
echo "Logs: ${LOG_DIR}"

if [[ "${AUTO_OPEN_BROWSER}" == "true" ]] && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:${HUB_PORT}/hub/index.html" >/dev/null 2>&1 || true
fi

wait "${PIDS[@]}"
