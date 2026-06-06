#!/usr/bin/env bash
# Purpose: Generate a draft .doc.md for a single source file.
# Docs: ../SKILL.md
#
# Thin wrapper around src/sin_codocs/generator.py that adds the sprint-specific
# safety rails:
#   - refuses to overwrite an existing .doc.md (unless --force)
#   - prints a one-line summary at the end
#
# Usage:
#   generate.sh <SOURCE_FILE> [--stdout] [--force]
#
# Exit codes:
#   0  draft created
#   1  .doc.md already exists (without --force)
#   2  source not found / unsupported extension
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GENERATOR="$SKILL_DIR/src/sin_codocs/generator.py"

[[ -f "$GENERATOR" ]] || { echo "Generator missing: $GENERATOR" >&2; exit 2; }

if [[ $# -lt 1 ]]; then
  sed -n '2,12p' "$0"
  exit 2
fi

SRC="$1"
STDOUT=0
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --stdout)  STDOUT=1 ;;
    --force)   FORCE=1 ;;
    --help|-h) sed -n '2,12p' "$0"; exit 0 ;;
    *)         ;;
  esac
done

[[ -f "$SRC" ]] || { echo "Source file not found: $SRC" >&2; exit 2; }

ARGS=("$SRC")
[[ $STDOUT -eq 1 ]] && ARGS+=("--stdout")
[[ $FORCE  -eq 1 ]] && ARGS+=("--overwrite")

python3 "$GENERATOR" "${ARGS[@]}"
rc=$?

if [[ $rc -ne 0 && $STDOUT -eq 0 ]]; then
  case $rc in
    1) echo "(refused: .doc.md already exists — pass --force to overwrite)" >&2 ;;
    2) echo "(source not found or unsupported extension)" >&2 ;;
  esac
fi
exit $rc
