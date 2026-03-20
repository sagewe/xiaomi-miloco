# Xiaomi Miloco Agent Guide

This file is the canonical working guide for coding agents in this repository.

## Scope

- Backend service: `miloco_server/`
- Shared Xiaomi device kit: `miot_kit/`
- Optional native agent runtime: `native/miloco-agent-runtime/`
- Frontend: `web_ui/`

The repository no longer contains a standalone AI engine service. Treat the backend as the primary runtime.

## Environment

Use these versions unless a task explicitly requires something else:

- Python: `3.12`
- Node.js: `>=20`
- npm: `>=9`
- Rust: stable toolchain, only needed when working on `native/miloco-agent-runtime`
- Docker: recent version with `docker compose`

Recommended local tooling:

- `uv` for Python environments and ad hoc test runs
- `maturin` for the native Python/Rust module

## Backend Setup

From the repository root:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ./miot_kit
uv pip install -e ./miloco_server
```

Start the backend:

```bash
python scripts/start_server.py
```

Useful config files:

- `config/server_config.yaml`
- `config/prompt_config.yaml`

## Rust Runtime Setup

Build the optional native runtime locally only when you are changing the Rust agent runtime or testing the Rust backend path:

```bash
uvx maturin develop --manifest-path native/miloco-agent-runtime/Cargo.toml
```

Select the runtime backend before starting the server:

```bash
export MILOCO_AGENT_RUNTIME_BACKEND=python
export MILOCO_AGENT_RUNTIME_BACKEND=rust
export MILOCO_AGENT_RUNTIME_BACKEND=auto
```

Notes:

- `python`: always use the Python chat runtime
- `rust`: require the native module to be installed
- `auto`: prefer the native module, otherwise fall back to Python

## Frontend Setup

Install and run the frontend only when the task touches `web_ui/`:

```bash
cd web_ui
npm install
npm run dev
```

If you need backend-only development, you can skip the frontend dev server. When a built frontend is required, run:

```bash
cd web_ui
npm run build
```

The build output is generated under `web_ui/dist/`. Copy those files into `miloco_server/static/` when the backend needs to serve the bundled UI.

## Tests

Common validation commands from the repository root:

```bash
python3 -m compileall miloco_server
```

```bash
PYTHONPATH=. uv run --with-editable ./miloco_server --with-editable ./miot_kit --with pytest --with pytest-asyncio pytest tests
```

Native runtime checks:

```bash
cargo test --manifest-path native/miloco-agent-runtime/Cargo.toml
```

Replay benchmark:

```bash
PYTHONPATH=. uv run --with aiohttp python scripts/benchmark_agent_runtime_replay.py --scenario tool_loop --iterations 20 --warmup 3
```

## Migration Workflow

When doing refactors or Rust migration work, use small issue-driven slices:

1. Create one GitHub issue for one isolated change.
2. Branch from `origin/main` using `codex/issue-<num>-<slug>`.
3. Make the smallest code change that closes the issue.
4. Run focused verification for the files and behavior you changed.
5. Open a PR with `Closes #<issue>`.
6. Merge, then look for the next naturally exposed issue.

Do not batch unrelated cleanup into the same PR.

## Current Migration Boundary

Already migrated or formalized:

- Rust runtime request contract
- Rust runtime event contract
- Tool invocation contract shared by Python and Rust bridge paths

Still Python-owned:

- `MCPClientManager`
- `ToolExecutor` execution backend
- FastAPI routing and WebSocket lifecycle
- DAO and chat history persistence

When in doubt, tighten contracts before moving more execution across the Python/Rust boundary.
