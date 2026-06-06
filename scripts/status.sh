#!/usr/bin/env bash
# Purpose: Show current CoDocs coverage status (human-readable).
# Docs: ../SKILL.md
#
# Wraps lib/metrics.py + lib/reporter.py to give a one-screen status
# for a repo. Faster than running the full sprint.
#
# Usage:
#   status.sh [REPO_PATH] [--json] [--min=N]
#
# Exit codes:
#   0  coverage >= --min (default 70)
#   1  coverage < --min
#   2  invalid args / repo not found
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
METRICS="$SKILL_DIR/src/sin_codocs/metrics.py"
REPORTER="$SKILL_DIR/src/sin_codocs/reporter.py"
LIB_DIR="$SKILL_DIR/lib"

REPO_PATH="."
JSON=0
MIN=70

for arg in "$@"; do
  case "$arg" in
    --json)    JSON=1 ;;
    --min=*)   MIN="${arg#--min=}" ;;
    --help|-h) sed -n '2,12p' "$0"; exit 0 ;;
    -*) echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)  REPO_PATH="$arg" ;;
  esac
done

[[ -d "$REPO_PATH" ]] || { echo "Not a directory: $REPO_PATH" >&2; exit 2; }
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

ARGS=(--path "$REPO_PATH" --min "$MIN")
[[ $JSON -eq 1 ]] && ARGS+=("--json")

if [[ $JSON -eq 1 ]]; then
  python3 "$METRICS" "${ARGS[@]}"
  exit $?
fi

# Human mode: run metrics JSON, format with reporter
TMP="$(mktemp -t sin-codocs-sprint-status.XXXXXX.json)"
trap 'rm -f "$TMP"' EXIT
python3 "$METRICS" --path "$REPO_PATH" --min "$MIN" --json > "$TMP" 2>/dev/null
rc=$?
[[ $rc -gt 1 ]] && { cat "$TMP"; exit $rc; }

python3 - "$TMP" "$LIB_DIR" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
from reporter import format_sprint_summary
from metrics import SprintReport

raw = json.loads(Path(sys.argv[1]).read_text())
sp = SprintReport(**{k: v for k, v in raw.items()
                     if k in SprintReport.__dataclass_fields__})
print()
print(format_sprint_summary(sp))
print()
PY

if [[ $rc -ne 0 ]]; then
  echo
  echo "Coverage is below the --min gate ($MIN%)."
  echo "Run: bash $REPO_PATH/../scripts/sprint.sh $REPO_PATH --auto"
  echo "(or wherever the sprint.sh lives — adjust the path)"
fi
exit $rc
