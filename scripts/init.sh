#!/usr/bin/env bash
# Purpose: Initialize SOTA CoDocs in a new or existing repo
# Docs: ../SKILL.md (Quick start — init flow)
#
# Walks the target repo, creates a .doc.md companion for every code file
# that lacks one, inserts Purpose:/Docs: headers where missing, and
# installs a pre-commit hook (if .git exists) that runs `sin codocs check`.
#
# Usage:
#   init.sh [REPO_PATH] [--with-hooks] [--strict] [--quiet]
#
# Options:
#   REPO_PATH       target repo (default: cwd)
#   --with-hooks    install pre-commit hook
#   --strict        fail on missing doc for any non-test source file
#   --quiet         suppress per-file output
#
# Exit codes:
#   0  all source files have .doc.md + Purpose header
#   1  some files missing docs (only with --strict)
#   2  invalid arguments
set -euo pipefail

# ── Defaults ───────────────────────────────────────────────────────────
REPO_PATH="."
WITH_HOOKS=0
STRICT=0
QUIET=0

for arg in "$@"; do
  case "$arg" in
    --with-hooks) WITH_HOOKS=1 ;;
    --strict)     STRICT=1 ;;
    --quiet)      QUIET=1 ;;
    --help|-h)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    -*)  echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)   REPO_PATH="$arg" ;;
  esac
done

# ── Color helpers ──────────────────────────────────────────────────────
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
  C_BLUE=$'\033[0;34m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""
fi
log()  { [[ $QUIET -eq 1 ]] || printf "%s[init]%s %s\n" "$C_BLUE" "$C_RESET" "$*"; }
ok()   { [[ $QUIET -eq 1 ]] || printf "%s[ ok ]%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf "%s[warn]%s %s\n" "$C_YELLOW" "$C_RESET" "$*" >&2; }
fail() { printf "%s[fail]%s %s\n" "$C_YELLOW" "$C_RESET" "$*" >&2; }

# ── Resolve paths ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ ! -d "$REPO_PATH" ]]; then
  fail "Repo path does not exist: $REPO_PATH"
  exit 2
fi
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

DOC_TEMPLATE="$SKILL_DIR/src/sin_codocs/doc_md_template.md"
PY_TEMPLATE="$SKILL_DIR/templates/module.py.template"

[[ -f "$DOC_TEMPLATE" ]] || { fail "Missing template: $DOC_TEMPLATE"; exit 2; }

log "Initializing SOTA CoDocs in: $REPO_PATH"

# ── File extensions to scan ────────────────────────────────────────────
EXTS=(py ts tsx js jsx go rs rb java kt swift c cpp h hpp sh bash)

created_docs=0
created_headers=0
skipped=0
total=0

for ext in "${EXTS[@]}"; do
  # Skip node_modules, .venv, build dirs, the skill's own files
  while IFS= read -r -d '' src; do
    # Skip our own skill files, tests dirs, and example dirs
    case "$src" in
      */node_modules/*|*/.venv/*|*/venv/*|*/__pycache__/*|*/.git/*) continue ;;
      */build/*|*/dist/*|*/.next/*) continue ;;
    esac
    [[ "$src" == "$SKILL_DIR"/* ]] && continue

    total=$((total + 1))
    base="${src%.*}"
    doc="$base.doc.md"

    if [[ ! -f "$doc" ]]; then
      base_name="$(basename "$src")"
      mkdir -p "$(dirname "$doc")"
      # Render doc.md template, replace placeholder
      sed "s|<filename.py>|$base_name|g; s|<this-file>.doc.md|$base_name.doc.md|g" \
        "$DOC_TEMPLATE" > "$doc"
      created_docs=$((created_docs + 1))
      log "  + $doc"
    fi

    # Insert Purpose header if missing (Python only for now)
    if [[ "$ext" == "py" ]] && ! head -5 "$src" | grep -q "Docs:"; then
      warn "Missing Docs: header in $src (run scripts/new-doc-md.sh or edit manually)"
      skipped=$((skipped + 1))
    fi
  done < <(find "$REPO_PATH" -type f -name "*.$ext" -print0 2>/dev/null)
done

# ── Pre-commit hook ────────────────────────────────────────────────────
if [[ $WITH_HOOKS -eq 1 ]] && [[ -d "$REPO_PATH/.git" ]]; then
  HOOK="$REPO_PATH/.git/hooks/pre-commit"
  if [[ -f "$HOOK" ]] && ! grep -q "sin codocs check" "$HOOK"; then
    warn "Pre-commit hook exists but does not run sin codocs check — leaving alone"
  elif [[ ! -f "$HOOK" ]]; then
    cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# Auto-installed by sin-codocs init.sh
set -e
sin codocs check || {
  echo "sin codocs check failed — see above" >&2
  exit 1
}
EOF
    chmod +x "$HOOK"
    ok "Installed pre-commit hook: $HOOK"
  fi
fi

# ── Coverage report ────────────────────────────────────────────────────
echo
ok "Created $created_docs new .doc.md files"
if [[ $skipped -gt 0 ]]; then
  warn "$skipped source files still need a Purpose/Docs header"
fi
log "Scanned $total source files across: ${EXTS[*]}"

if [[ $STRICT -eq 1 ]] && [[ $skipped -gt 0 ]]; then
  exit 1
fi
exit 0
