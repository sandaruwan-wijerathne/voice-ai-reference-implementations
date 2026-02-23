# LiveKit Custom Nova 2 (Quick Start)

Small demo for running an Amazon Nova Sonic voice agent with LiveKit.

## 1) Prerequisites

- Python 3.13+
- `uv`
- LiveKit server + `lk` CLI installed
- Node.js + npm (only if you want to test with local `ui`)

## 2) Configure `.env`

Create `.env` in this folder:

```bash
AWS_REGION=us-east-1
AWS_NOVA_SONIC_MODEL=amazon.nova-2-sonic-v1:0

LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

Do not store AWS credentials in `.env` if you want interactive prompts each run.

## 3) Start LiveKit server (optional)

Only needed if you want to run components manually. `./run-all.sh` starts it automatically (or reuses an existing one).

```bash
livekit-server --dev
```

## 4) Install Python dependencies

In terminal 2:

```bash
uv sync
```

## 5) Start agent + frontend with one command

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
- UI URL: `http://localhost:3002`
- LiveKit server: starts with `livekit-server --dev` if not already running
- Agent mode: `connect` with auto-reconnect loop (recommended for local reload/rejoin)
- Agent health port: dynamic (`LIVEKIT_AGENT_PORT=0`) to avoid 8081 conflicts

Optional overrides:

```bash
UI_PORT=3005 AGENT_SCRIPT=agent_with_tool.py LIVEKIT_AGENT_PORT=8181 ./run-all.sh
```

Run worker mode (if you want server-side dispatch model):

```bash
AGENT_MODE=start ./run-all.sh
```

## 6) Run only the agent (optional)

```bash
uv run python agent.py connect --room my-first-room
```

Optional (tool-calling example):

```bash
uv run python agent_with_tool.py connect --room my-first-room
```

## 7) Quick test (local UI)

```bash
cd ui
npm install
npm start
```

Then open `http://localhost:3000` (manual run) or `http://localhost:3002` (when using `run-all.sh`).

`npm start` runs `scripts/prepare-livekit-env.sh`, which:
- generates a LiveKit token using `lk token create`
- writes `REACT_APP_LIVEKIT_SERVER_URL` and `REACT_APP_LIVEKIT_TOKEN` to `ui/.env`

So you do not need the hosted playground flow for basic local testing.

## Unified 4-app hub

From `integration_demos/`, you can launch all demos and the shared dashboard:

```bash
./run-all-demos.sh
```
