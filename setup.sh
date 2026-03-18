#!/bin/bash
# Miloco Setup Script
# Sets up and runs miloco_server using external LLM API (no AI Engine needed)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── uv check ──────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
info "uv $(uv --version) ✓"

# ── Node.js check ─────────────────────────────────────────────────────────────
info "Checking Node.js..."
if ! command -v node &>/dev/null; then
    error "Node.js not found. Install via: https://nodejs.org or your system package manager"
fi
NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
    error "Node.js >= 20 required, found $(node -v)"
fi
info "Node.js $(node -v) ✓"

# ── Install Python dependencies ────────────────────────────────────────────────
info "Installing Python dependencies..."
uv sync
info "Dependencies ready ✓"

# ── Optional native runtime wheel ──────────────────────────────────────────────
if [ "${MILOCO_AGENT_RUNTIME_BACKEND:-python}" != "python" ]; then
    info "Attempting to install the optional miloco-agent-runtime wheel..."
    uv run python scripts/install_miloco_agent_runtime.py || warn "Native runtime wheel install failed; Python backend remains available"
fi

# ── Build frontend ─────────────────────────────────────────────────────────────
STATIC_DIR="miloco_server/static"
if [ -f "$STATIC_DIR/index.html" ]; then
    info "Frontend already built, skipping. (delete $STATIC_DIR to rebuild)"
else
    info "Installing frontend dependencies..."
    cd web_ui
    npm install -q
    info "Building frontend..."
    npm run build
    cd "$SCRIPT_DIR"

    info "Copying frontend build to miloco_server/static/..."
    mkdir -p "$STATIC_DIR"
    cp -r web_ui/dist/. "$STATIC_DIR/"
    info "Frontend ready ✓"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Setup complete! Start the server with:"
echo ""
echo "  uv run python scripts/start_server.py"
echo ""
echo "  Then open: https://127.0.0.1:8000"
echo ""
echo "  Next steps:"
echo "  1. Log in and go to Settings → Models"
echo "  2. Add your LLM API (OpenAI, DeepSeek, etc.)"
echo "     - Base URL: https://api.openai.com/v1"
echo "     - API Key: sk-..."
echo "  3. Set the model as active for 'planning'"
echo "============================================================"
