#!/bin/bash
# Reign Launcher for macOS/Linux
# Double-click or run: ./start.sh

cd "$(dirname "$0")"

echo "Starting Reign..."
echo "Open http://localhost:8000 in your browser"
echo "Press Ctrl+C to stop"
echo ""

# Try uv first, fallback to python -m reign
if command -v uv &> /dev/null; then
    uv run python -m reign
else
    python -m reign
fi
