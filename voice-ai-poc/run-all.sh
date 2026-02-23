#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/vs-voice-ai-backend"
FRONTEND_DIR="${ROOT_DIR}/vs-voice-ai-frontend"
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

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "Error: backend directory not found at ${BACKEND_DIR}"
  exit 1
fi

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "Error: frontend directory not found at ${FRONTEND_DIR}"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm is not installed or not on PATH."
  exit 1
fi

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

load_env_if_unset "${SHARED_ENV_FILE}"
load_env_if_unset "${PROJECT_ENV_FILE}"

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

BACKEND_PID=""
cleanup() {
  echo
  echo "Stopping services..."
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting backend (vs-voice-ai-backend/launch.sh)..."
(
  cd "${BACKEND_DIR}"
  bash ./launch.sh
) &
BACKEND_PID=$!

PREFERRED_UI_PORT="${UI_PORT:-5174}"
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

echo "Starting frontend on http://localhost:${UI_PORT} ..."
cd "${FRONTEND_DIR}"
npm run dev -- --strictPort --port "${UI_PORT}"
