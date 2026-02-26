#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHARED_ENV_FILE="${ROOT_DIR}/../.env.shared"
PROJECT_ENV_FILE="${ROOT_DIR}/.env"

load_env_if_unset() {
  local env_file="$1"
  local line=""
  local key=""
  local value=""

  [[ -f "${env_file}" ]] || return 0
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    [[ "${line}" == export[[:space:]]* ]] && line="${line#export }"
    if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      if [[ -z "${!key+x}" ]]; then
        eval "export ${key}=${value}"
      fi
    fi
  done < "${env_file}"
}

ensure_set() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "Error: ${var_name} is required. Set it in exported env vars, ${SHARED_ENV_FILE}, or ${PROJECT_ENV_FILE}."
    exit 1
  fi
}

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is not installed or not on PATH."
  exit 1
fi

load_env_if_unset "${SHARED_ENV_FILE}"
load_env_if_unset "${PROJECT_ENV_FILE}"

ensure_set "LIVEKIT_URL"
ensure_set "LIVEKIT_API_KEY"
ensure_set "LIVEKIT_API_SECRET"
ensure_set "DEEPGRAM_API_KEY"
ensure_set "OPENAI_API_KEY"
ensure_set "CARTESIA_API_KEY"

AGENT_MODE="${AGENT_MODE:-dev}"
if [[ "${AGENT_MODE}" != "dev" && "${AGENT_MODE}" != "start" && "${AGENT_MODE}" != "console" ]]; then
  echo "Error: AGENT_MODE must be one of: dev, start, console"
  exit 1
fi

echo "Starting Traditional LiveKit Agent in ${AGENT_MODE} mode..."
cd "${ROOT_DIR}"
if [[ "${AGENT_MODE}" == "dev" ]]; then
  uv run python src/agent.py dev --no-reload
else
  uv run python src/agent.py "${AGENT_MODE}"
fi
