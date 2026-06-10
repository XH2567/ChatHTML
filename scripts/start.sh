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

# Wait for backend to be ready
sleep 3

# Start frontend
echo "[Frontend] Starting Vite dev server..."
cd "$PROJECT_DIR/frontend/paper-workflow"
npm run dev

# Cleanup: stop backend when frontend exits
echo "Stopping backend..."
kill $BACKEND_PID 2>/dev/null
wait $BACKEND_PID 2>/dev/null
echo "ChatHTML stopped."
