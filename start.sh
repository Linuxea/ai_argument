#!/bin/bash

# AI Argument - Startup Script
# Usage: ./start.sh [port]

set -e

PORT=${1:-8000}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"

echo "Installing Python dependencies ..."
"$PIP" install -r "$SCRIPT_DIR/requirements.txt"

echo "Starting server on port $PORT ..."
exec "$PYTHON" -m uvicorn main:app --reload --port "$PORT" --app-dir "$SCRIPT_DIR"
