#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$REPO_ROOT/html"

mkdir -p "$OUTPUT_DIR"
mkdir -p "$REPO_ROOT/diagrams"

# Symlink icon package into diagrams/ so D2 can resolve relative icon paths
ICON_SRC="$REPO_ROOT/html/aws-icon-package"
ICON_LINK="$REPO_ROOT/diagrams/aws-icon-package"
if [ -d "$ICON_SRC" ] && [ ! -L "$ICON_LINK" ]; then
    ln -s "$ICON_SRC" "$ICON_LINK"
fi

if [ ! -f "$REPO_ROOT/diagrams/main.d2" ]; then
    echo "Error: No D2 files found. Run 'python3 scripts/aws_to_d2.py' first."
    exit 1
fi

echo "Converting diagrams/main.d2 -> $OUTPUT_DIR/main.html"
cd "$REPO_ROOT/diagrams"
d2 main.d2 "$OUTPUT_DIR/main.html"
cd "$REPO_ROOT"

echo "Done. Output in $OUTPUT_DIR"
