#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$DIR/.." && pwd)"

echo "=== Starting ChatHTML ==="
echo ""

# Start backend
echo "[Backend] Starting Rust server..."
cd "$PROJECT_DIR/backend/paper-workflow"
cargo run &
BACKEND_PID=$!

sleep 3

# Start frontend
echo "[Frontend] Starting Vite dev server..."
cd "$PROJECT_DIR/frontend/paper-workflow"
npm run dev

# Cleanup
echo "Stopping backend..."
kill $BACKEND_PID 2>/dev/null
wait $BACKEND_PID 2>/dev/null
echo "ChatHTML stopped."
