#!/usr/bin/env bash
# Purpose: Measure CoDocs coverage % for a repo
# Docs: ../SKILL.md
#
# Computes four metrics:
#   1. % of source files with a .doc.md companion
#   2. % of source files with a Purpose/Docs header
#   3. % of public functions with a docstring
#   4. Average inline comment density (lines_comment / lines_code)
#
# Usage:
#   coverage.sh [REPO_PATH] [--json] [--min=N]
#
# Exit codes:
#   0  coverage >= --min (default 70)
#   1  coverage < --min
#   2  invalid args
set -euo pipefail

REPO_PATH="."
JSON=0
MIN=70

for arg in "$@"; do
  case "$arg" in
    --json)   JSON=1 ;;
    --min=*)  MIN="${arg#--min=}" ;;
    --help|-h)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    -*) echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)  REPO_PATH="$arg" ;;
  esac
done

[[ -d "$REPO_PATH" ]] || { echo "Not a directory: $REPO_PATH" >&2; exit 2; }
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

# ── Delegate to the Python metrics library ────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METRICS_LIB="$SCRIPT_DIR/../src/sin_codocs/metrics.py"

if [[ ! -f "$METRICS_LIB" ]]; then
  echo "Missing metrics lib: $METRICS_LIB" >&2
  exit 2
fi

ARGS=("--path" "$REPO_PATH" "--min" "$MIN")
[[ $JSON -eq 1 ]] && ARGS+=("--json")

python3 "$METRICS_LIB" "${ARGS[@]}"
rc=$?

if [[ $rc -ne 0 && $JSON -eq 0 ]]; then
  echo
  echo "Coverage below $MIN% — see numbers above. Improve by:"
  echo "  • bash scripts/init.sh $REPO_PATH  (create missing .doc.md)"
  echo "  • Add Purpose:/Docs: header to source files"
  echo "  • Add docstrings to public functions"
fi
exit $rc
