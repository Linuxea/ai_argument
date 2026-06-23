#!/bin/bash

# AI Argument - Startup Script
# Usage: ./start.sh [port]

set -e

PORT=${1:-8000}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_VERSION="${PYTHON_VERSION:-3.14}"

PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple}"
PYPI_TRUSTED_HOST="${PYPI_TRUSTED_HOST:-mirrors.aliyun.com}"

if command -v uv >/dev/null 2>&1; then
    HAVE_UV=1
else
    HAVE_UV=0
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment at $VENV_DIR ..."
    if [ "$HAVE_UV" -eq 1 ]; then
        uv venv "$VENV_DIR" --python "$PYTHON_VERSION"
    else
        python3 -m venv "$VENV_DIR"
    fi
fi

PYTHON="$VENV_DIR/bin/python"

echo "Installing Python dependencies ..."
if [ "$HAVE_UV" -eq 1 ]; then
    uv pip install --python "$PYTHON" \
        --index-url "$PYPI_INDEX_URL" \
        --trusted-host "$PYPI_TRUSTED_HOST" \
        -r "$SCRIPT_DIR/requirements.txt"
else
    "$PYTHON" -m pip install \
        --index-url "$PYPI_INDEX_URL" \
        --trusted-host "$PYPI_TRUSTED_HOST" \
        -r "$SCRIPT_DIR/requirements.txt"
fi

echo "Starting server on port $PORT ..."
exec "$PYTHON" -m uvicorn main:app --reload --port "$PORT" --app-dir "$SCRIPT_DIR"
