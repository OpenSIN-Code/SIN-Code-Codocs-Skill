#!/usr/bin/env bash
# Purpose: Create a SOTA .doc.md companion for a single source file
# Docs: ../SKILL.md
#
# Reads the source file's Purpose/Docs header (if present), takes the
# first ~50 lines for context, and generates a .doc.md template pre-filled
# with the file name. Then opens it in $EDITOR for human completion.
#
# Usage:
#   new-doc-md.sh <path-to-source-file>
#
# Supported extensions: py, ts, tsx, js, jsx, go, rs, rb, java, kt, swift
#
# Exit codes:
#   0  doc file created (or already existed)
#   1  source file missing
#   2  unsupported extension
#   3  write failed
set -euo pipefail

if [[ $# -lt 1 ]]; then
  sed -n '2,16p' "$0"
  exit 2
fi

SRC="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$SKILL_DIR/src/sin_codocs/doc_md_template.md"

[[ -f "$SRC" ]] || { echo "Source file not found: $SRC" >&2; exit 1; }
[[ -f "$TEMPLATE" ]] || { echo "Template not found: $TEMPLATE" >&2; exit 2; }

ext="${SRC##*.}"
case "$ext" in
  py|ts|tsx|js|jsx|go|rs|rb|java|kt|swift) ;;
  *) echo "Unsupported extension: .$ext" >&2; exit 2 ;;
esac

base="${SRC%.*}"
doc="$base.doc.md"
fname="$(basename "$SRC")"

# If doc already exists, refuse to overwrite
if [[ -f "$doc" ]]; then
  echo "Already exists: $doc"
  echo "Edit it directly: $EDITOR $doc"
  exit 0
fi

# Render the template — replace the placeholders, leave the rest intact
mkdir -p "$(dirname "$doc")"
sed "s|<filename.py>|$fname|g; s|<this-file>.doc.md|$fname.doc.md|g" \
  "$TEMPLATE" > "$doc"

echo "Created: $doc"
echo "  → Edit it to fill in: What it does, Dependencies, Config, Examples, Caveats"
echo
echo "Preview:"
echo "------"
head -20 "$doc"
echo "------"

# Open in editor if available
if [[ -n "${EDITOR:-}" ]] && command -v "$EDITOR" >/dev/null 2>&1; then
  "$EDITOR" "$doc"
elif command -v code >/dev/null 2>&1; then
  code "$doc"
fi
