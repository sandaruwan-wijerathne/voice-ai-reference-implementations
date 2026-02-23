# Bedrock Core Nova 2 (Quick Start)

Small WebSocket server demo for Amazon Nova Sonic.

## 1) Prerequisites

- Python 3.13+
- `uv`
- AWS credentials with Bedrock access

## 2) Configure `.env`

Create `.env` in this folder:

```bash
AWS_REGION=us-east-1
AWS_NOVA_SONIC_MODEL=amazon.nova-2-sonic-v1:0

HOST=localhost
WS_PORT=8081
HEALTH_PORT=8082
```

Do not store AWS credentials in `.env` if you want interactive prompts each run.

## 3) Install dependencies

```bash
uv sync
```

## 4) Start frontend + backend with one command

Make the launcher executable once:

```bash
chmod +x run-all.sh
```

Start both services:

```bash
./run-all.sh
```

The script prompts for:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`

If these env vars already exist, the script uses them and only prompts for missing ones.
Use `./run-all.sh -p` to force manual re-entry.

It starts:
- Backend: `uv run server.py`
- Frontend: `npm start` (from `ui/`) on `http://localhost:3001`

You can override the UI port if needed:

```bash
UI_PORT=3005 ./run-all.sh
```

## 5) Start only backend (optional)

```bash
uv run server.py
```

Server endpoints:
- WebSocket: `ws://localhost:8081`
- Health check: `http://localhost:8082/health`

## 6) Optional agent modes

Run with MCP integration:

```bash
uv run python server.py --agent mcp
```

Run with Strands agent integration:

```bash
uv run python server.py --agent strands
```

## Unified 4-app hub

From `integration_demos/`, you can launch all demos and the shared dashboard:

```bash
./run-all-demos.sh
```
