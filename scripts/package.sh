#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$DIR/.." && pwd)"
RELEASE_DIR="$PROJECT_DIR/chathtml-release"

if [ ! -d "$RELEASE_DIR" ]; then
    echo "Error: $RELEASE_DIR does not exist. Run build-release.sh first."
    exit 1
fi

echo "=== Packaging ChatHTML Release ==="

cd "$PROJECT_DIR"

ARCHIVE_NAME="chathtml-release-$(date +%Y%m%d).tar.gz"

tar -czf "$ARCHIVE_NAME" -C "$(dirname "$RELEASE_DIR")" "$(basename "$RELEASE_DIR")"

echo "Created: $ARCHIVE_NAME"
echo "Size: $(du -h "$ARCHIVE_NAME" | cut -f1)"
