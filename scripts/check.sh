#!/usr/bin/env bash
# Purpose: Run `sin codocs check` and render a clear summary
# Docs: ../SKILL.md
#
# Wraps the bundle CLI and translates its output into a human-friendly
# pass/fail summary. Use --strict in CI to fail on any broken reference.
#
# Usage:
#   check.sh [REPO_PATH] [--strict] [--json]
#
# Exit codes:
#   0  no broken references
#   1  broken references found (always with --strict, otherwise warning)
#   2  sin CLI not installed
set -euo pipefail

REPO_PATH="."
STRICT=0
JSON=0
QUIET=0

for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    --json)   JSON=1 ;;
    --quiet)  QUIET=0 ;;  # placeholder
    --help|-h)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    -*) echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)  REPO_PATH="$arg" ;;
  esac
done

# ── Color helpers ──────────────────────────────────────────────────────
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
  C_RED=$'\033[0;31m'; C_BLUE=$'\033[0;34m'
else
  C_RESET=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""
fi
ok()   { printf "%s[ ok ]%s %s\n" "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf "%s[warn]%s %s\n" "$C_YELLOW" "$C_RESET" "$*" >&2; }
err()  { printf "%s[fail]%s %s\n" "$C_RED"   "$C_RESET" "$*" >&2; }
info() { printf "%s[info]%s %s\n" "$C_BLUE"  "$C_RESET" "$*"; }

# ── Locate sin CLI ─────────────────────────────────────────────────────
SIN_BIN="${SIN_BIN:-$(command -v sin || true)}"
if [[ -z "$SIN_BIN" ]]; then
  # Try common Python install locations
  for cand in "$HOME/.local/bin/sin" "/usr/local/bin/sin" \
              "$HOME/.local/share/uv/tools/sin-code-bundle/bin/sin"; do
    [[ -x "$cand" ]] && SIN_BIN="$cand" && break
  done
fi

if [[ -z "$SIN_BIN" ]]; then
  err "sin CLI not found. Install with: pipx install sin-code-bundle"
  exit 2
fi

info "Using: $SIN_BIN"
info "Path:  $REPO_PATH"

# ── Run check ──────────────────────────────────────────────────────────
cd "$REPO_PATH"
set +e
RAW=$("$SIN_BIN" codocs check --json 2>&1)
RC=$?
set -e

if [[ $JSON -eq 1 ]]; then
  echo "$RAW"
  exit $RC
fi

# ── Parse JSON summary ────────────────────────────────────────────────
total=0
broken=0
ok_count=0
if command -v python3 >/dev/null 2>&1 && [[ -n "$RAW" ]]; then
  summary=$(printf '%s' "$RAW" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get('files') or data.get('results') or []
    else:
        rows = []
    total  = len(rows)
    broken = sum(1 for r in rows if r.get('status') == 'broken' or r.get('broken'))
    ok_c   = total - broken
    print(f'{total} {broken} {ok_c}')
except Exception:
    print('0 0 0')
" 2>/dev/null)
  total=$(echo "$summary" | awk '{print $1}')
  broken=$(echo "$summary" | awk '{print $2}')
  ok_count=$(echo "$summary" | awk '{print $3}')
fi

# Fall back to plain text output if no JSON parseable
if [[ $total -eq 0 ]]; then
  echo "$RAW"
  if [[ $RC -ne 0 ]]; then
    if [[ $STRICT -eq 1 ]]; then
      exit 1
    fi
    warn "check.sh: sin codocs check exited $RC (use --strict to fail in CI)"
    exit 0
  fi
  ok "All references resolve"
  exit 0
fi

# ── Report ─────────────────────────────────────────────────────────────
echo
printf "  Total references:  %d\n" "$total"
printf "  Resolved:          %s%d%s\n" "$C_GREEN" "$ok_count" "$C_RESET"
printf "  Broken:            %s%d%s\n" \
  "$([[ $broken -gt 0 ]] && echo "$C_RED" || echo "$C_GREEN")" \
  "$broken" "$C_RESET"

if [[ $broken -gt 0 ]]; then
  err "Found $broken broken .doc.md reference(s)"
  if [[ $STRICT -eq 1 ]]; then
    exit 1
  fi
  warn "Re-run with --strict to fail in CI"
  exit 0
fi
ok "All .doc.md references resolve"
exit 0
