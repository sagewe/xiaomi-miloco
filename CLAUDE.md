# CLAUDE.md — Xiaomi Miloco Codebase Guide

**Xiaomi Miloco** (Local Copilot) is an AI-powered smart home platform that combines Xiaomi MIoT camera vision, a local/cloud LLM agent, and IoT device control. This document provides AI assistants with the context needed to work effectively in this codebase.

---

## Repository Overview

```
xiaomi-miloco/
├── miloco_server/      # Python FastAPI backend (main service)
├── miot_kit/           # Xiaomi MIoT SDK (local dependency)
├── native/             # Optional Rust agent runtime (miloco-agent-runtime)
├── web_ui/             # React 18 frontend (Vite + Ant Design)
├── config/             # YAML configuration files
├── docker/             # Dockerfile and docker-compose files
├── scripts/            # Dev/install/benchmark scripts
├── tests/              # Backend integration tests
└── docs/               # Setup and usage documentation
```

---

## Architecture

### Backend: `miloco_server/`

A **FastAPI + uvicorn** application structured in layers:

| Layer | Location | Purpose |
|-------|----------|---------|
| **Controller** | `controller/` | HTTP/WebSocket route handlers |
| **Service** | `service/` | Business logic |
| **DAO** | `dao/` | SQLAlchemy database access (SQLite) |
| **Proxy** | `proxy/` | External system connectors (MIoT, Home Assistant, LLM) |
| **Agent** | `agent/` | ReAct-style chat and automation agents |
| **MCP** | `mcp/` | Model Context Protocol client and tool execution |
| **Schema** | `schema/` | Pydantic data models |
| **Config** | `config/` | YAML config loading and constants |
| **Middleware** | `middleware/` | Auth (JWT), exception handling |
| **Utils** | `utils/` | Camera vision, chat history, LLM utilities |
| **Tools** | `tools/` | Agent tool implementations (vision, rule creation) |

### Service Manager Singleton

`miloco_server/service/manager.py` — `Manager` is a global singleton that owns and exposes all services, DAOs, and proxies. Use `get_manager()` everywhere rather than constructing services directly.

### Agent System

Two agent types, both subclassing `ChatAgent`:

- **`ChatAgent`** (`agent/chat_agent.py`) — Handles live user chat queries. Implements a ReAct loop (think → tool-call → observe) up to `agent_max_steps` iterations (default: 10).
- **`ActionDescriptionDynamicExecuteAgent`** (`agent/dynamic_execute_agent.py`) — Executes pre-defined action descriptions for trigger-rule automation.

**Dual runtime backends:**
- **Python** (default): `ChatAgent._cyclic_execute()` runs the ReAct loop in pure Python.
- **Rust** (`native/miloco-agent-runtime`): Optional native wheel (`miloco_agent_runtime`) loaded lazily via `RustRuntimeAdapter`. Controlled by `MILOCO_AGENT_RUNTIME_BACKEND` env var or `config/server_config.yaml → chat.agent_runtime_backend`.
  - Values: `python` | `rust` | `auto` (prefers Rust, falls back to Python if not installed).

**Runtime bridge:** `agent/runtime_bridge.py` — `AgentRuntimeBridge` exposes Python callbacks (`emit_event`, `invoke_tool`) to the Rust runtime via a JSON event contract defined in `agent/runtime_contract.py`.

### MCP (Model Context Protocol)

- `mcp/mcp_client_manager.py` — Manages multiple MCP clients (local default + user-configured).
- `mcp/tool_executor.py` — Parses LLM tool-call requests and dispatches to the correct MCP client.
- `mcp/local_mcp_servers.py` — Built-in MCP server definitions.
- Tool invocation contract: `mcp/tool_contract.py`.

### Chat via WebSocket

`controller/chat_controller.py` — Chat is handled over WebSocket (`/api/chat/ws/query`). The client sends `Event` JSON objects; the server dispatches them through `ChatAgentDispatcher`.

### Trigger Rules

Cron-style automation rules stored in SQLite. `service/trigger_rule_runner.py` polls every 2 seconds (configurable), evaluates rules against camera images using a vision LLM, and executes actions via the tool executor.

### Models

Two LLM roles configured separately via the Model Management UI:
- **Planning** (`ModelPurpose.PLANNING`) — Main chat/reasoning LLM.
- **Vision** — Camera frame analysis LLM.

Both accessed through `proxy/llm_proxy.py` (OpenAI-compatible API).

### Frontend: `web_ui/`

React 18 SPA served by the FastAPI backend as static files at build time.

- **Build tool:** Vite 6
- **UI library:** Ant Design 5 + `@ant-design/x`
- **State management:** Zustand
- **i18n:** react-i18next
- **Testing:** Vitest + Testing Library + MSW (mock service worker)
- **Styling:** CSS Modules + Less

Pages: `Home`, `Instant` (chat), `Setting`, `ModelManage`, `McpService`, `SmartCenter` (triggers), `LogManage`, `Setup`.

---

## Configuration

### Primary Config: `config/server_config.yaml`

All runtime configuration lives here. Key sections:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"          # set to "debug" for verbose logs

chat:
  agent_max_steps: 10
  agent_runtime_backend: "python"   # "python" | "rust" | "auto"

trigger_rule_runner:
  interval_seconds: 2
  request_timeout_seconds: 30       # increase if LLM API is slow

miot:
  cloud_server: "cn"        # "cn" | "de" | "i2" | "ru" | "sg" | "us"
```

### Environment Variable Overrides

| Variable | Description |
|----------|-------------|
| `MILOCO_SERVER_STORAGE_DIR` | Override storage path (DB, images, certs, logs) |
| `MILOCO_AGENT_RUNTIME_BACKEND` | Override agent backend (`python`/`rust`/`auto`) |
| `BACKEND_HOST` | Override server host |
| `BACKEND_PORT` | Override server port |
| `BACKEND_LOG_LEVEL` | Override log level |
| `SECRET_KEY` | JWT signing secret (change in production) |

### Prompt Config: `config/prompt_config.yaml`

System prompts for chat and trigger evaluation, accessed via `PromptConfig` in `miloco_server/config/prompt_config.py`.

---

## Development Workflows

### Backend Setup

```bash
# 1. Install miot_kit (local dependency)
cd miot_kit && pip install -e . && cd ..

# 2. Install miloco_server
cd miloco_server && pip install -e . && cd ..

# 3. (Optional) copy frontend build to static dir
cp -r web_ui/dist/* miloco_server/static/

# 4. Start server
python scripts/start_server.py
# API docs at https://127.0.0.1:8000/docs
```

> **Package manager:** The root `pyproject.toml` uses `uv`. Run `uv sync` to install all dependencies. Use `uv run` to execute scripts.

### Frontend Setup

```bash
cd web_ui
npm install

# Development server (requires backend running)
# Edit web_ui/config.js to set backend proxy target
npm run dev      # https://127.0.0.1:5173

# Production build
npm run build    # outputs to web_ui/dist/
```

### Optional: Rust Runtime

```bash
# Build native wheel (requires stable Rust toolchain)
uvx maturin develop --manifest-path native/miloco-agent-runtime/Cargo.toml

# Enable Rust backend
export MILOCO_AGENT_RUNTIME_BACKEND=rust
python scripts/start_server.py
```

### Docker

```bash
# Full stack
docker compose -f docker/docker-compose.yaml up

# Lite (no GPU)
docker compose -f docker/docker-compose-lite.yaml up
```

---

## Testing

### Backend Tests

```bash
# Run from project root
pytest tests/
```

Key test files:
- `tests/test_runtime_contract.py` — Runtime JSON contract serialization
- `tests/test_tool_contract.py` — Tool invocation contract
- `tests/test_dispatcher_event_loop_bridge.py` — Dispatcher/bridge integration
- `tests/test_miloco_agent_runtime.py` — Native runtime integration (skipped if wheel absent)

### Frontend Tests

```bash
cd web_ui
npm run test          # run once
npm run test:watch    # watch mode
npm run test:ui       # Vitest UI
```

Tests live in `web_ui/tests/` with MSW mocks in `web_ui/tests/mocks/`.

### Benchmark

```bash
# Validate Rust runtime latency
uv run --with aiohttp python scripts/benchmark_agent_runtime_replay.py \
  --scenario tool_loop --iterations 20 --warmup 3
```

---

## Code Conventions

### Python

- **Style:** `black` (line length 88, Python 3.12 target); `flake8` for linting; `pylint` with `.pylintrc`.
- **Minimum Python version:** 3.12 (`match`, `type X = Y`, etc. are available).
- **Logging:** Use `logger = logging.getLogger(__name__)` per module. Prefix log messages with `[request_id]` inside agents: `logger.info("[%s] message", self._request_id, ...)`.
- **Exceptions:** Use custom exception classes from `middleware/exceptions.py` (`ResourceNotFoundException`, `ValidationException`, `ConflictException`, `BusinessException`, `LLMServiceException`).
- **Async:** FastAPI endpoints are `async`. Agent methods that call LLMs are `async`. Synchronous DAO operations are fine (SQLite with `check_same_thread=False`).
- **Imports inside methods:** Allowed to break circular imports (e.g., `from miloco_server.service.manager import get_manager` inside `__init__`).
- **Copyright header:** All Python files begin with `# Copyright (C) 2025 Xiaomi Corporation`.

### Commit Messages

Follow Conventional Commits:

```
<type>: <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `revert`.

- Subject: imperative mood, lowercase first letter, no period.
- Body: required for all types except `docs`; explain *why*.

### Naming

- Xiaomi brand: use `xiaomi`/`mi` in variables; `mihome`/`MiHome` for Xiaomi Home.
- MIoT protocol: `miot`/`MIoT`.
- Home Assistant: always "Home Assistant" in prose; `hass`/`hass_xxx` in variables.

### JavaScript/JSX

- ESLint with project config at `web_ui/eslint.config.js`.
- React hooks rules enforced (`eslint-plugin-react-hooks`).
- CSS Modules with `.module.less` files per component.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `miloco_server/main.py` | FastAPI app setup, startup/shutdown hooks |
| `miloco_server/service/manager.py` | Global service singleton (`get_manager()`) |
| `miloco_server/agent/chat_agent.py` | Core ReAct agent loop |
| `miloco_server/agent/runtime_bridge.py` | Rust↔Python bridge callbacks |
| `miloco_server/agent/rust_runtime_adapter.py` | Lazy Rust module loader |
| `miloco_server/agent/runtime_contract.py` | JSON event contract types |
| `miloco_server/mcp/tool_executor.py` | Tool dispatch layer |
| `miloco_server/mcp/mcp_client_manager.py` | MCP client lifecycle |
| `miloco_server/proxy/llm_proxy.py` | OpenAI-compatible LLM wrapper |
| `miloco_server/service/trigger_rule_runner.py` | Automation rule scheduler |
| `miloco_server/config/normal_config.py` | Config constants (paths, server, chat) |
| `config/server_config.yaml` | Primary runtime configuration |
| `config/prompt_config.yaml` | LLM system prompts |
| `web_ui/src/pages/` | React page components |

---

## Important Constraints

- **Non-commercial license:** This project is limited to non-commercial use only (see `LICENSE.md`). Do not add or suggest commercial integrations.
- **Linux/Windows (WSL2) only:** macOS is not officially supported. Hardware requires NVIDIA GPU (30-series+, 8GB VRAM min) for local model inference.
- **Python 3.12+ required.**
- **Do not push secrets:** `config/server_config.yaml` contains the default JWT secret (`your-super-secret-key-change-this`); ensure it is overridden via `SECRET_KEY` env var in production. Never commit real API keys.
- **Single repo version:** `0.1.0` is used across `pyproject.toml` (root), `miloco_server/pyproject.toml`, and `native/miloco-agent-runtime`. Keep them in sync on release.
