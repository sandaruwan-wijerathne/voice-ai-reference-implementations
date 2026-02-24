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

ensure_set "DEEPGRAM_API_KEY"
ensure_set "OPENAI_API_KEY"
ensure_set "CARTESIA_API_KEY"
ensure_set "VOICE_SYSTEM_PROMPT"

UI_PORT="${UI_PORT:-7861}"
UI_HOST="${UI_HOST:-0.0.0.0}"

echo "Starting Traditional Pipecat Pipeline on http://localhost:${UI_PORT} ..."
cd "${ROOT_DIR}"
uv run bot.py --host "${UI_HOST}" --port "${UI_PORT}"
