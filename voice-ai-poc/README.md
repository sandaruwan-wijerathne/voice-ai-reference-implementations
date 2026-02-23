# POC Demo Launcher

This folder contains:
- `vs-voice-ai-backend`
- `vs-voice-ai-frontend`

## Start POC backend + frontend

```bash
chmod +x run-all.sh
./run-all.sh
```

The launcher prompts for AWS credentials and starts both services together.
If the AWS env vars already exist, it only prompts for missing ones.
Use `./run-all.sh -p` to force manual re-entry.

## Unified 4-app hub

From `integration_demos/`, you can launch all demos and the shared dashboard:

```bash
./run-all-demos.sh
```
