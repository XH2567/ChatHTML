#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
echo "=== ChatHTML Server ==="
echo "Backend API:  http://127.0.0.1:8000/api"
echo "Frontend UI:  http://127.0.0.1:8000"
echo ""
exec ./chat-html
