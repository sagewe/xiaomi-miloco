#!/bin/bash
# Miloco Mac Setup Script
# Sets up and runs miloco_server on macOS using external LLM API (no AI Engine needed)

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

# ── Python check ──────────────────────────────────────────────────────────────
info "Checking Python version..."
PYTHON=$(command -v python3 || command -v python || error "Python not found. Install Python >= 3.11 first.")
PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    error "Python >= 3.11 required, found $PY_VERSION"
fi
info "Python $PY_VERSION ✓"

# ── Node.js check ─────────────────────────────────────────────────────────────
info "Checking Node.js..."
if ! command -v node &>/dev/null; then
    error "Node.js not found. Install via: brew install node"
fi
NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
    error "Node.js >= 20 required, found $(node -v)"
fi
info "Node.js $(node -v) ✓"

# ── Python virtual environment ────────────────────────────────────────────────
info "Setting up Python virtual environment..."
if command -v uv &>/dev/null; then
    INSTALLER="uv"
    if [ ! -d ".venv" ]; then
        uv venv .venv --python "$PYTHON"
    fi
    source .venv/bin/activate
    PIP="uv pip"
else
    if [ ! -d ".venv" ]; then
        $PYTHON -m venv .venv
    fi
    source .venv/bin/activate
    PIP="pip"
    pip install --upgrade pip -q
fi
info "Virtual environment ready ✓"

# ── Install miot_kit ───────────────────────────────────────────────────────────
info "Installing miot_kit..."
$PIP install -e ./miot_kit -q
info "miot_kit installed ✓"

# ── Install miloco_server ──────────────────────────────────────────────────────
info "Installing miloco_server..."
$PIP install -e ./miloco_server -q
info "miloco_server installed ✓"

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
echo "  source .venv/bin/activate"
echo "  python scripts/start_server.py"
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
