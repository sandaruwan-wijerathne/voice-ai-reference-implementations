# Integration Demos Unified Launcher

Run all implementations and open a single dashboard page:

```bash
chmod +x run-all-demos.sh
./run-all-demos.sh
```

Use `-p` to force re-entering AWS values manually even if env vars are already set:

```bash
./run-all-demos.sh -p
```

## Recommended env strategy

Use a shared env file for secrets/API keys:

```bash
cp .env.shared.example .env.shared
```

Then keep per-project `.env` files for app-specific non-secret config (ports, URLs, model IDs).

Precedence used by launchers:

1. Already exported shell variables
2. `integration_demos/.env.shared`
3. Project-local `.env`
4. Script defaults or prompt (for missing required values)

`VOICE_SYSTEM_PROMPT` is required and is used as the single system prompt across the integrated demos.

## What it does

- Uses existing environment values if present; prompts only for missing values.
- Loads shared env values from `.env.shared` when present.
- Prompts once for:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_SESSION_TOKEN`
  - optional `AWS_REGION` (default `us-east-1`)
- Starts all demo launchers in the background.
- Starts a unified hub at `http://localhost:8090/hub/index.html`.
- Waits for each UI to become reachable before printing ready status.
- On `Ctrl+C`, stops all launched processes and releases acquired ports.

## Default ports

- Hub: `8090`
- Realtime Bedrock UI: `3001`
- Realtime LiveKit UI: `3002`
- Realtime Pipecat UI: `5173`
- Voice AI POC UI: `5174`
- Traditional Pipecat Pipeline UI: `7861`
- Traditional LiveKit Agent: worker mode (no local web UI)
  - Hub embeds a lightweight LiveKit test client at `/agent-starter-client.html`

## Optional environment overrides

```bash
BEDROCK_UI_PORT=3101 LIVEKIT_UI_PORT=3102 PIPECAT_UI_PORT=5273 POC_UI_PORT=5274 PIPECAT_QUICKSTART_UI_PORT=8861 HUB_PORT=8091 ./run-all-demos.sh
```

Useful options:
- `LIVEKIT_ROOM=demo-room`
- `AGENT_STARTER_ROOM=agent-starter-room`
- `AUTO_OPEN_BROWSER=false`
- `WAIT_TIMEOUT_SECONDS=120`

## Logs

Runtime logs are written to:

```bash
integration_demos/.logs/
```

Files:
- `bedrock.log`
- `livekit.log`
- `pipecat.log`
- `voice-ai-poc.log`
- `traditional-pipecat-pipeline.log`
- `traditional-livekit-agent.log`
- `hub.log`

## Troubleshooting

- `Port already in use`: stop old processes using that port, or override ports with env vars.
- Microphone issues inside embedded apps:
  - use `http://localhost` URLs only,
  - allow browser microphone permission,
  - if needed, click each panel's **Open** button and grant permission in that tab.
- If one app fails to start, inspect the corresponding file in `.logs/`.
