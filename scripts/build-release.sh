#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$DIR/.." && pwd)"
RELEASE_DIR="$PROJECT_DIR/chathtml-release"

echo "=== Building ChatHTML Release ==="

echo ""
echo "--- Building frontend ---"
cd "$PROJECT_DIR/frontend/paper-workflow"
npm install
npm run build

echo ""
echo "--- Building backend ---"
cd "$PROJECT_DIR/backend/paper-workflow"
cargo build --release

echo ""
echo "--- Assembling release package ---"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

cp "$PROJECT_DIR/backend/paper-workflow/target/release/chat-html" "$RELEASE_DIR/"

cp -r "$PROJECT_DIR/frontend/paper-workflow/dist" "$RELEASE_DIR/dist"

cp "$PROJECT_DIR/backend/paper-workflow/ai_config.json" "$RELEASE_DIR/"

cp "$DIR/release-README.md" "$RELEASE_DIR/README.md"

cat > "$RELEASE_DIR/start.sh" << 'SCRIPT'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
echo "=== ChatHTML Server ==="
echo "Backend API:  http://127.0.0.1:8000/api"
echo "Frontend UI:  http://127.0.0.1:8000"
echo ""
exec ./chat-html
SCRIPT

chmod +x "$RELEASE_DIR/start.sh"
chmod +x "$RELEASE_DIR/chat-html"

echo ""
echo "=== Release ready at: $RELEASE_DIR ==="
echo "Size:"
du -sh "$RELEASE_DIR"
