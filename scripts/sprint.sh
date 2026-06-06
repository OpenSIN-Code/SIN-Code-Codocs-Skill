#!/usr/bin/env bash
# Purpose: Run a full CoDocs coverage sprint on a repo.
# Docs: ../SKILL.md
#
# The 4-step sprint pipeline:
#   1. SCAN      — find every CoDocs gap (src/sin_codocs/scanner.py)
#   2. REPORT    — format the gap table (src/sin_codocs/reporter.py)
#   3. GENERATE  — auto-create draft .doc.md for each gap (src/sin_codocs/generator.py)
#   4. COMMIT    — git commit, only if --commit was passed
#
# Usage:
#   sprint.sh <REPO_PATH> [--auto] [--dry-run] [--commit] [--no-scan-update]
#
# Flags:
#   --auto             generate draft .doc.md for every MISSING_COMPANION gap
#   --dry-run          print the plan, do NOT write any files
#   --commit           git add -A && git commit at the end (interactive prompt before committing)
#   --no-scan-update   skip the before/after scan updates (faster, less informative)
#   --min=N            coverage gate (default 70)
#
# Exit codes:
#   0  sprint completed
#   1  repo not found / not a git repo (only relevant with --commit)
#   2  invalid arguments
#   3  upstream sin-codocs metrics missing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCANNER="$SKILL_DIR/src/sin_codocs/scanner.py"
GENERATOR="$SKILL_DIR/src/sin_codocs/generator.py"
METRICS="$SKILL_DIR/src/sin_codocs/metrics.py"
REPORTER="$SKILL_DIR/src/sin_codocs/reporter.py"
CHECKLIST="$SKILL_DIR/templates/sprint_checklist.md"

REPO_PATH=""
AUTO=0
DRY_RUN=0
COMMIT=0
SCAN_UPDATE=1
MIN=70

for arg in "$@"; do
  case "$arg" in
    --auto)             AUTO=1 ;;
    --dry-run)          DRY_RUN=1 ;;
    --commit)           COMMIT=1 ;;
    --no-scan-update)   SCAN_UPDATE=0 ;;
    --min=*)            MIN="${arg#--min=}" ;;
    --help|-h) sed -n '2,22p' "$0"; exit 0 ;;
    -*) echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)   REPO_PATH="$arg" ;;
  esac
done

# ── Pre-flight ─────────────────────────────────────────────────────────
[[ -n "$REPO_PATH" ]] || { echo "Usage: sprint.sh <REPO_PATH> [--auto] [--dry-run] [--commit]" >&2; exit 2; }
[[ -d "$REPO_PATH" ]] || { echo "Not a directory: $REPO_PATH" >&2; exit 1; }
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

[[ -f "$SCANNER"   ]] || { echo "Scanner missing"   >&2; exit 1; }
[[ -f "$GENERATOR" ]] || { echo "Generator missing" >&2; exit 1; }
[[ -f "$METRICS"   ]] || { echo "Metrics missing"   >&2; exit 1; }

# Check upstream
if ! python3 -c "import sys; sys.path.insert(0,'$SKILL_DIR/../sin-codocs/src/sin_codocs'); import metrics" 2>/dev/null; then
  echo "WARN: sin-codocs upstream not on sys.path — will use subprocess" >&2
fi

# ── Color helpers ──────────────────────────────────────────────────────
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  C_RESET=$'\033[0m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
  C_BLUE=$'\033[0;34m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""
fi
log()  { printf "%s[sprint]%s %s\n" "$C_BLUE"   "$C_RESET" "$*"; }
ok()   { printf "%s[ ok  ]%s %s\n" "$C_GREEN"  "$C_RESET" "$*"; }
warn() { printf "%s[warn ]%s %s\n" "$C_YELLOW" "$C_RESET" "$*" >&2; }
hdr()  { printf "\n%s%s== %s ==%s\n" "$C_BOLD" "$C_BLUE" "$*" "$C_RESET"; }

# ── Step 1: SCAN ──────────────────────────────────────────────────────
hdr "Step 1/4: SCAN"
log "Scanning $REPO_PATH"

SCAN_TMP="$(mktemp -t sin-codocs-sprint-scan.XXXXXX.json)"
BEFORE_TMP=""
AFTER_TMP=""
trap 'rm -f "$SCAN_TMP" "$BEFORE_TMP" "$AFTER_TMP"' EXIT

python3 "$SCANNER" --path "$REPO_PATH" --json > "$SCAN_TMP"

# Save before-state for the diff (only if we'll be modifying anything)
if [[ $AUTO -eq 1 || $COMMIT -eq 1 ]] && [[ $SCAN_UPDATE -eq 1 ]]; then
  BEFORE_TMP="$(mktemp -t sin-codocs-sprint-before.XXXXXX.json)"
  python3 "$METRICS" --path "$REPO_PATH" --min "$MIN" --json > "$BEFORE_TMP" 2>/dev/null || true
fi

# Print the human-friendly table
python3 - "$SCAN_TMP" "$SKILL_DIR/src/sin_codocs" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
from reporter import format_gap_table
from scanner import ScanResult

raw = json.loads(Path(sys.argv[1]).read_text())
sr = ScanResult(repo_path=raw["repo_path"],
                scanned_count=raw["scanned_count"],
                by_kind=raw["by_kind"])
print(format_gap_table(sr))
PY

# ── Step 2: REPORT (also done by Step 1) ─────────────────────────────
hdr "Step 2/4: REPORT"
log "Coverage before sprint:"
python3 "$METRICS" --path "$REPO_PATH" --min "$MIN" || true

# ── Step 3: GENERATE ─────────────────────────────────────────────────
hdr "Step 3/4: GENERATE"
if [[ $AUTO -eq 0 ]]; then
  log "Skipped (pass --auto to enable draft generation)"
  log "Run bash scripts/diff.sh $REPO_PATH to preview what would be created"
elif [[ $DRY_RUN -eq 1 ]]; then
  log "DRY-RUN — would create:"
  bash "$SCRIPT_DIR/diff.sh" "$REPO_PATH" --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for g in data['gaps']:
    if g['kind'] == 'MISSING_COMPANION':
        print(f'  + {g[\"rel_path\"]} → {g[\"suggested_doc\"].split(chr(47))[-1]}')
"
else
  created=0
  skipped=0
  while IFS= read -r -d '' gap_json; do
    rel_path=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['rel_path'])" "$gap_json")
    full_path="$REPO_PATH/$rel_path"
    doc_path="${full_path%.*}.doc.md"
    if [[ -f "$doc_path" ]]; then
      skipped=$((skipped + 1))
      continue
    fi
    if python3 "$GENERATOR" "$full_path" >/dev/null 2>&1; then
      created=$((created + 1))
    else
      warn "Failed: $rel_path"
    fi
  done < <(python3 -c "
import json
data = json.load(open('$SCAN_TMP'))
for g in data['gaps']:
    if g['kind'] == 'MISSING_COMPANION':
        print(json.dumps(g), end='\0')
")

  ok "Created $created draft .doc.md files"
  if [[ $skipped -gt 0 ]]; then
    log "Skipped $skipped (already had .doc.md)"
  fi
fi

# ── Step 4: COMMIT ────────────────────────────────────────────────────
hdr "Step 4/4: COMMIT"
if [[ $COMMIT -eq 0 ]]; then
  log "Skipped (pass --commit to git commit the drafts)"
  log "Suggested commit message:"
  echo "  docs(coverage): CoDocs coverage sprint"
elif [[ $DRY_RUN -eq 1 ]]; then
  log "Skipped (dry-run)"
elif [[ ! -d "$REPO_PATH/.git" ]]; then
  warn "Not a git repo — skipping commit. Drafts are on disk."
else
  log "Staging new .doc.md files…"
  git -C "$REPO_PATH" add $(find "$REPO_PATH" -name "*.doc.md" -newer "$SCAN_TMP" -type f 2>/dev/null) 2>/dev/null || \
    git -C "$REPO_PATH" add -A
  if [[ $SCAN_UPDATE -eq 1 ]] && [[ -f "${BEFORE_TMP:-}" ]]; then
    AFTER_TMP="$(mktemp -t sin-codocs-sprint-after.XXXXXX.json)"
    python3 "$METRICS" --path "$REPO_PATH" --min "$MIN" --json > "$AFTER_TMP" 2>/dev/null || true
    log "Coverage delta:"
    python3 - "$BEFORE_TMP" "$AFTER_TMP" "$SKILL_DIR/src/sin_codocs" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from reporter import format_diff
from metrics import SprintReport
b = json.loads(Path(sys.argv[1]).read_text())
a = json.loads(Path(sys.argv[2]).read_text())
before = SprintReport(**{k: v for k, v in b.items() if k in SprintReport.__dataclass_fields__})
after  = SprintReport(**{k: v for k, v in a.items() if k in SprintReport.__dataclass_fields__})
print(format_diff(before, after))
PY
  fi
  log "Committing (message: 'docs(coverage): CoDocs coverage sprint')…"
  git -C "$REPO_PATH" commit -m "docs(coverage): CoDocs coverage sprint" -m "Auto-generated draft .doc.md companions for files missing them." -m "Reviewers: see templates/sprint_checklist.md to fill in the human parts."
  ok "Committed."
fi

# ── Wrap-up ───────────────────────────────────────────────────────────
hdr "Sprint complete"
log "Next steps for the human reviewer:"
echo "  1. Open each new .doc.md in your editor"
echo "  2. Fill in the <TODO: …> placeholders (see templates/sprint_checklist.md)"
echo "  3. Run scripts/status.sh $REPO_PATH to see updated coverage"
echo
if [[ -f "$CHECKLIST" ]]; then
  log "Checklist: $CHECKLIST"
fi
