#!/usr/bin/env bash
# Purpose: SOTA-init a brand new Python module (file + companion doc)
# Docs: ../SKILL.md
#
# Combines new-doc-md.sh + the module.py template:
#   1. Creates the .py file from templates/module.py.template
#   2. Creates the matching .doc.md
#   3. Opens both in $EDITOR
#
# Usage:
#   new-module.sh <path/to/module.py>
#   new-module.sh src/services/auth.py
#
# Exit codes:
#   0  module created
#   1  target exists
#   2  invalid args / missing templates
set -euo pipefail

if [[ $# -lt 1 ]]; then
  sed -n '2,14p' "$0"
  exit 2
fi

TARGET="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PY_TEMPLATE="$SKILL_DIR/templates/module.py.template"
DOC_TEMPLATE="$SKILL_DIR/src/sin_codocs/doc_md_template.md"

[[ -f "$PY_TEMPLATE" ]]  || { echo "Missing: $PY_TEMPLATE"  >&2; exit 2; }
[[ -f "$DOC_TEMPLATE" ]] || { echo "Missing: $DOC_TEMPLATE" >&2; exit 2; }

# Reject if file already exists (refuse to clobber)
if [[ -e "$TARGET" ]]; then
  echo "Refusing to overwrite: $TARGET" >&2
  exit 1
fi

ext="${TARGET##*.}"
[[ "$ext" == "py" ]] || { echo "new-module.sh only generates .py modules" >&2; exit 2; }

base="${TARGET%.*}"
doc="$base.doc.md"
modname="$(basename "$TARGET" .py)"

# Path relative to repo root (best-effort heuristic for "Docs: <path>")
rel_path="$TARGET"
if [[ "$TARGET" = /* ]]; then
  # Strip CWD prefix for cleaner doc reference
  cwd="$(pwd)"
  case "$TARGET" in
    "$cwd"/*) rel_path="${TARGET#$cwd/}" ;;
  esac
fi

mkdir -p "$(dirname "$TARGET")"

# ── Render .py file ────────────────────────────────────────────────────
# <module_path> in the template should be the bare module name (no
# extension) — the template adds ".doc.md" itself. So we substitute
# with `basename` only.
modstem="$(basename "$TARGET" .py)"
sed -e "s|<module_name>|$modstem|g" \
    -e "s|<module_path>|$modstem|g" \
    "$PY_TEMPLATE" > "$TARGET"

# ── Render .doc.md ─────────────────────────────────────────────────────
fname="$(basename "$TARGET")"
sed -e "s|<filename.py>|$fname|g" \
    -e "s|<this-file>.doc.md|$fname.doc.md|g" \
    "$DOC_TEMPLATE" > "$doc"

echo "Created:"
echo "  $TARGET"
echo "  $doc"
echo
echo "→ Open in editor to customize:"
echo "    \$EDITOR $TARGET $doc"
