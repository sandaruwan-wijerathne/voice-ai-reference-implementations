# Third-Party Notices

This repository contains code adapted from official upstream examples and SDK starter projects.
Use this file to preserve attribution and license context when copying, modifying, or redistributing upstream code.

## How to use this file

- Keep this file in the repository root.
- For each imported example/starter, record:
  - upstream project and URL,
  - local path in this repo,
  - license,
  - what was changed locally.
- Keep original license headers/files in copied code where required by license terms.

## Included third-party components

### 1) LiveKit Agents Starter (Python)

- **Upstream project:** LiveKit Agents Starter - Python
- **Upstream URL:** `https://github.com/livekit-examples/agent-starter-python`
- **Local path:** `traditional-livekit-agent/`
- **License:** MIT (confirmed from `traditional-livekit-agent/LICENSE`)
- **Copyright notice:** Copyright (c) 2025 LiveKit, Inc.
- **Local modifications:** Project path rename, launcher/hub integration, local runtime wiring for unified demo hub.

### 2) Pipecat Quickstart

- **Upstream project:** Pipecat Quickstart
- **Upstream URL:** `https://github.com/pipecat-ai/pipecat-quickstart`
- **Local path:** `traditional-pipecat-pipeline/`
- **License:** Verify in upstream repository before public redistribution (no top-level license file detected in local copy).
- **Local modifications:** Project path rename, custom launch orchestration, unified hub integration and runtime settings.

### 3) Other official example-derived demo folders

The following folders are used for approach/framework evaluation and include code that may be based on official examples:

- `realtime-bedrock-nova2/`
- `realtime-livekit-nova2/`
- `realtime-pipecat-nova2/`
- `voice-ai-poc/`

For each folder above, confirm and document:

- upstream repository URL,
- license type and required notices,
- specific local modifications.

## Recommended attribution snippet (README)

Use this short block in your root `README.md`:

> This repository contains integrations and evaluation work built on top of official example projects from LiveKit, Pipecat, and related SDK ecosystems.  
> See `THIRD_PARTY_NOTICES.md` for upstream links, licenses, and local modifications.

