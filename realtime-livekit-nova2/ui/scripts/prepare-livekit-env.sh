#!/usr/bin/env bash
set -euo pipefail

if [ -x /home/linuxbrew/.linuxbrew/bin/brew ]; then
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
fi

if ! command -v lk >/dev/null 2>&1; then
  echo "Error: LiveKit CLI (lk) is not installed or not in PATH."
  echo "Install it with: brew install livekit livekit-cli"
  exit 1
fi

if [ ! -d node_modules ] || [ ! -x node_modules/.bin/react-scripts ]; then
  echo "Installing React dependencies..."
  npm install
fi

OUTPUT=$(lk token create \
  --api-key devkey --api-secret secret \
  --join --room my-first-room --identity "user-$(date +%s)-$RANDOM" \
  --valid-for 24h)

LIVEKIT_TOKEN=$(printf "%s\n" "$OUTPUT" | sed -n 's/^Access token: //p')

if [ -z "$LIVEKIT_TOKEN" ]; then
  echo "Error: Failed to parse LiveKit token from lk output."
  echo "$OUTPUT"
  exit 1
fi

{
  echo "REACT_APP_LIVEKIT_SERVER_URL=ws://localhost:7880"
  echo "REACT_APP_LIVEKIT_TOKEN=$LIVEKIT_TOKEN"
} > .env

echo "Updated .env with LiveKit server URL and token."
