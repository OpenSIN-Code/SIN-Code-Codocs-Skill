#!/usr/bin/env bash
# Purpose: Install the sin-codocs-sprint skill — symlink, verify deps, smoke-test.
# Docs: SKILL.md
#
# Mirrors the ceo-audit install-skill.sh pattern:
#   1. Symlink the source into ~/.config/opencode/skills/sin-codocs-sprint
#   2. chmod +x every scripts/*.sh
#   3. Verify python3 + upstream sin-codocs skill present
#   4. Smoke-test scripts/scan.sh on the skill's own directory
#
# Usage:
#   install-skill.sh [--force] [--dry-run] [--source=DIR] [--skip-smoke]
#
# Flags:
#   --force          re-link even if destination already exists
#   --dry-run        print what would happen, do not change the filesystem
#   --source=DIR     use DIR as the skill source (default: this skill's root)
#   --skip-smoke     skip the final scan.sh smoke test
#
# Exit codes:
#   0  install (or already installed) succeeded
#   1  dependency missing (python3 or upstream sin-codocs)
#   2  filesystem error (link failed, permission denied)
#   3  smoke test failed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST_DIR="${HOME}/.config/opencode/skills/sin-codocs-sprint"
UPSTREAM_SKILL_DIR="${HOME}/.config/opencode/skills/sin-codocs"
FORCE=0
DRY_RUN=0
SKIP_SMOKE=0
SOURCE_DIR="$SKILL_ROOT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)      FORCE=1; shift ;;
    --dry-run)    DRY_RUN=1; shift ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --source=*)   SOURCE_DIR="${1#*=}"; shift ;;
    -h|--help)    sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

# ── Color helpers ──────────────────────────────────────────────────────
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_RED=$'\033[0;31m'; C_GREEN=$'\033[0;32m'
  C_YELLOW=$'\033[1;33m'; C_BLUE=$'\033[0;34m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""
fi
ok()    { printf "%s[OK]%s    %s\n" "$C_GREEN"  "$C_RESET" "$*"; }
info()  { printf "%s[INFO]%s  %s\n" "$C_BLUE"   "$C_RESET" "$*"; }
warn()  { printf "%s[WARN]%s  %s\n" "$C_YELLOW" "$C_RESET" "$*"; }
err()   { printf "%s[FAIL]%s  %s\n" "$C_RED"    "$C_RESET" "$*" >&2; }
heading(){ printf "\n%s%s== %s ==%s\n" "$C_BOLD" "$C_BLUE" "$*" "$C_RESET"; }

# ── Pre-flight ─────────────────────────────────────────────────────────
heading "sin-codocs-sprint — install"
if [[ ! -d "$SOURCE_DIR" ]]; then
  err "Source directory not found: $SOURCE_DIR"
  exit 2
fi
if [[ ! -x "$SOURCE_DIR/scripts/sprint.sh" ]]; then
  err "sprint.sh is missing or not executable: $SOURCE_DIR/scripts/sprint.sh"
  exit 2
fi
info "Source:      $SOURCE_DIR"
info "Destination: $DEST_DIR"
[[ $DRY_RUN -eq 1 ]] && info "Mode:        DRY-RUN (no changes)"
[[ $FORCE  -eq 1 ]] && info "Flag:        --force (will re-link)"
[[ $SKIP_SMOKE -eq 1 ]] && info "Flag:        --skip-smoke"

# ── Step 1: Symlink ────────────────────────────────────────────────────
heading "Step 1/4: Symlink"
if [[ "$SOURCE_DIR" == "$DEST_DIR" ]] || [[ "$(cd "$SOURCE_DIR" 2>/dev/null && pwd)" == "$(cd "$DEST_DIR" 2>/dev/null && pwd)" ]]; then
  ok "Source IS the destination (already installed in-place) → $SOURCE_DIR"
elif [[ -L "$DEST_DIR" ]]; then
  CURRENT_TARGET="$(readlink "$DEST_DIR" 2>/dev/null || true)"
  if [[ "$CURRENT_TARGET" == "$SOURCE_DIR" ]]; then
    ok "Link already correct → $CURRENT_TARGET"
  else
    if [[ $FORCE -eq 1 ]]; then
      if [[ $DRY_RUN -eq 1 ]]; then
        info "[DRY] would rm $DEST_DIR (currently → $CURRENT_TARGET)"
        info "[DRY] would ln -s $SOURCE_DIR $DEST_DIR"
      else
        rm "$DEST_DIR"
        ln -s "$SOURCE_DIR" "$DEST_DIR"
        ok "Re-linked → $SOURCE_DIR"
      fi
    else
      warn "Link exists but points elsewhere: $CURRENT_TARGET"
      warn "  re-run with --force to replace"
    fi
  fi
elif [[ -e "$DEST_DIR" ]]; then
  if [[ $FORCE -eq 1 ]]; then
    if [[ $DRY_RUN -eq 1 ]]; then
      info "[DRY] would rm -rf $DEST_DIR (regular file/dir)"
      info "[DRY] would ln -s $SOURCE_DIR $DEST_DIR"
    else
      rm -rf "$DEST_DIR"
      ln -s "$SOURCE_DIR" "$DEST_DIR"
      ok "Replaced regular file/dir with symlink → $SOURCE_DIR"
    fi
  else
    err "Destination exists and is not a symlink: $DEST_DIR"
    err "  re-run with --force to replace"
    exit 2
  fi
else
  if [[ $DRY_RUN -eq 1 ]]; then
    info "[DRY] would mkdir -p $(dirname "$DEST_DIR")"
    info "[DRY] would ln -s $SOURCE_DIR $DEST_DIR"
  else
    mkdir -p "$(dirname "$DEST_DIR")"
    ln -s "$SOURCE_DIR" "$DEST_DIR"
    ok "Linked → $SOURCE_DIR"
  fi
fi

# ── Step 2: Permissions ────────────────────────────────────────────────
heading "Step 2/4: Permissions"
if [[ $DRY_RUN -eq 1 ]]; then
  info "[DRY] would chmod +x scripts/*.sh"
else
  for s in "$SOURCE_DIR"/scripts/*.sh; do
    [[ -f "$s" ]] || continue
    if [[ ! -x "$s" ]]; then
      chmod +x "$s"
      ok "chmod +x $(basename "$s")"
    fi
  done
  ok "All scripts/*.sh are executable"
fi

# ── Step 3: Dependency check ──────────────────────────────────────────
heading "Step 3/4: Dependency check"
MISSING=0
if command -v python3 >/dev/null 2>&1; then
  ok "python3: $(command -v python3)"
else
  err "python3: MISSING"
  MISSING=$((MISSING+1))
fi
if [[ -f "$UPSTREAM_SKILL_DIR/src/sin_codocs/metrics.py" ]]; then
  ok "upstream sin-codocs: $UPSTREAM_SKILL_DIR/src/sin_codocs/metrics.py"
else
  warn "upstream sin-codocs: NOT FOUND (some features will fail)"
  warn "  install: see https://github.com/SIN-Rotator/SIN-Code-Bundle or"
  warn "           clone ~/.config/opencode/skills/sin-codocs"
  MISSING=$((MISSING+1))
fi
if command -v git >/dev/null 2>&1; then
  ok "git: $(command -v git) (only needed for --commit)"
else
  warn "git: missing (--commit will be disabled)"
fi

if [[ $MISSING -gt 0 ]] && [[ $DRY_RUN -eq 0 ]] && [[ $SKIP_SMOKE -eq 0 ]]; then
  err "$MISSING critical dependency missing — sprint will fail"
  # Don't exit: --skip-smoke + --dry-run should still be useful
fi

# ── Step 4: Smoke test ─────────────────────────────────────────────────
heading "Step 4/4: Smoke test"
if [[ $SKIP_SMOKE -eq 1 ]]; then
  info "Smoke test skipped (--skip-smoke)"
else
  if [[ $DRY_RUN -eq 1 ]]; then
    info "[DRY] would run: bash $SOURCE_DIR/scripts/scan.sh $SOURCE_DIR | head -3"
  else
    if OUT="$(bash "$SOURCE_DIR/scripts/scan.sh" "$SOURCE_DIR" 2>&1 | head -5)"; then
      if [[ -n "$OUT" ]]; then
        ok "scan.sh produced output"
        printf "       %s\n" "$(echo "$OUT" | head -1)"
      else
        err "scan.sh produced empty output"
        exit 3
      fi
    else
      err "scan.sh exited non-zero"
      exit 3
    fi
  fi
fi

heading "Install complete"
ok "Source:      $SOURCE_DIR"
ok "Destination: $DEST_DIR"
ok "Missing deps: $MISSING"
if [[ $DRY_RUN -eq 1 ]]; then
  warn "DRY-RUN: no changes were made"
fi
echo ""
echo "Try it:"
echo "  bash $SOURCE_DIR/scripts/scan.sh $SOURCE_DIR | head"
echo "  bash $SOURCE_DIR/scripts/status.sh $SOURCE_DIR"
echo ""
