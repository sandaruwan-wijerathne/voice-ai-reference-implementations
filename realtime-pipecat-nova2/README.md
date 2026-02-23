# Pipecat Custom Nova 2 (Quick Start)

Small demo for running a Pipecat voice bot with AWS Nova Sonic and testing it locally.

## 1) Prerequisites

- Python 3.13+
- `uv` installed
- Node.js + npm (only for browser test client)

## 2) Configure environment

Create `.env` in this folder:

```bash
AWS_REGION=us-east-1
AWS_NOVA_SONIC_MODEL=amazon.nova-2-sonic-v1:0

TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token

LOCAL_SERVER_URL=https://your-ngrok-url.ngrok-free.app
BOT_TYPE=websocket
```

Do not store AWS credentials in `.env` if you want interactive prompts each run.

Notes:
- Use `BOT_TYPE=websocket` for local browser testing.
- Set `BOT_TYPE=twilio` only when testing Twilio call flow.

## 3) Install dependencies

```bash
uv sync
```

## 4) Start backend + frontend with one command

Make the launcher executable once:

```bash
chmod +x run-all.sh
```

Run both services:

```bash
./run-all.sh
```

The script prompts for:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`

If these env vars already exist, the script uses them and only prompts for missing ones.
Use `./run-all.sh -p` to force manual re-entry.

Defaults:
- Backend: `uv run server.py`
- Frontend URL: `http://localhost:5173`
- If `5173` is busy, the launcher auto-selects the next free port and prints the exact URL.

Optional override:

```bash
UI_PORT=5175 ./run-all.sh
```

## 5) Start only backend (optional)

```bash
uv run server.py
```

Server runs on `http://localhost:7860`.

## 6) Quick local test (browser)

In a new terminal:

```bash
cd ui
npm install
npm run dev
```

Open `http://localhost:5173` and start speaking to test the bot.

## Unified 4-app hub

From `integration_demos/`, you can launch all demos and the shared dashboard:

```bash
./run-all-demos.sh
```
