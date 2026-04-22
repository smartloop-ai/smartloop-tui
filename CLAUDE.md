# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Smartloop

Smartloop (`slp`) is an AI assistant CLI and TUI for inferencing and fine-tuning small language models (SLMs) on edge devices. It runs a local API server that manages model lifecycle (download, load, inference, LoRA fine-tuning, GGUF conversion) and communicates with it over HTTP/SSE.

## Build & Run

```bash
make build          # creates .venv, installs deps + GPU backend (Metal/CUDA), installs project editable
make test           # verifies CLI help and GPU offload detection
make pack           # build + PyInstaller binary (dist/slp/slp)
make pack CUDA=1    # force CUDA backend on Linux/Windows
make clean          # remove .venv, build artifacts, caches
```

After `make build`, run via the symlink `./slp` or `.venv/bin/slp`.

## Architecture

### CLI layer (`commands/`)

`commands/cli.py` defines `main()` which parses args and creates a `CommandHandler`. `CommandHandler` uses **mixin inheritance** — it inherits from `InitCommand`, `ModelCommand`, `RunCommand`, `TokenCommand`, `ServerCommand` (all extending `Command` base class). `dispatch()` routes the subcommand to the appropriate mixin's `execute()`.

Key commands: `init` (model download via SSE streaming), `run` (launches TUI or CLI chat), `status`/`train`/`build` (model operations), `server` (start/stop/restart/status), `token` (credential management).

The `Command` base class (`commands/base.py`) auto-starts the API server if not running (`_require_server`) and provides shared helpers for server health checks and project resolution.

Shared singletons (`commands/console.py`): `console` (Rich), `logger`, `settings` (from `smartloop.config.AppSettings`).

### TUI layer (`tui/`)

Built with **Textual**. `SLPChat` (`tui/chat.py`) also uses mixin inheritance, composing:
- **Command mixins** (`tui/commands/`): `MCP`, `Document`, `Project`, `Skill`, `ModelInfo`, `Attachment`, `Auth` — each handles a `/slash-command` group
- **Worker mixins** (`tui/workers/`): `Connection`, `Bootstrap`, `Streaming` — background tasks for server communication
- **Widgets** (`tui/widgets/`): `ChatLog`, `CommandMenu`, `PromptTextArea`, `SelectableStatic`

Styling via `tui/css/chat.tcss`. Theme colors in `tui/theme.py`.

### Server (`smartloop` package — installed dependency)

The `smartloop` pip package (from private PyPI at `us-central1-python.pkg.dev/smartloop-gcp-us-east/slp-pypi`) provides the API server, model management, auth, and configuration. This repo contains the CLI/TUI client only.

### Packaging

`smartloop.spec` — PyInstaller spec for building the standalone binary. Runtime hooks in `hooks/` (telemetry disable, UTF-8 encoding). Release workflow (`.github/workflows/release.yml`) builds for macOS (arm64, signed+notarized), Linux (amd64, CUDA), and Windows (amd64, CUDA), triggered by `v*` tags.

## Key Patterns

- **Client-server**: CLI/TUI never runs models directly. All model operations go through HTTP to the local API server (default `127.0.0.1`, dynamic port via port file).
- **SSE streaming**: Model downloads (`/v1/init`, `/v1/bootstrap`), training, and chat completions all use Server-Sent Events.
- **Mixin composition**: Both `CommandHandler` and `SLPChat` are assembled from independent mixin classes rather than using delegation.
- **Auto-bootstrap**: Running `slp` with no server starts it automatically and bootstraps a default model if needed.

## Environment Variables

- `SLP_DEVELOPER_TOKEN` — developer token (alternative to `slp token set` or `-t` flag)
- `SLP_BASE_MODEL_NAME` — default model name
- `SLP_PROJECT_ID` / `SLP_PROJECT_NAME` — project selection
- `API_HOST` / `API_PORT` — server bind address
