#!/bin/bash

# AI Argument - Startup Script
# Usage: ./start.sh [port]

PORT=${1:-8000}

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Starting server on port $PORT..."
python -m uvicorn main:app --reload --port "$PORT"
