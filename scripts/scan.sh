#!/usr/bin/env bash
# Purpose: Scan a repo for CoDocs gaps (read-only).
# Docs: ../SKILL.md
#
# Walks a directory tree and prints a structured gap report. By
# default the report is human-readable text; pass --json to get
# machine-readable output for piping into other tools.
#
# Usage:
#   scan.sh [REPO_PATH] [--json] [--kind=KIND] [--quiet]
#
# Options:
#   REPO_PATH       target repo (default: cwd)
#   --json          emit JSON instead of human text
#   --kind=KIND     filter to one kind: MISSING_COMPANION | MISSING_HEADER | MISSING_DOCSTRING
#   --quiet         suppress per-file listing, only show the table
#
# Exit codes:
#   0  scan succeeded (gaps or not)
#   1  repo path not found / not a directory
#   2  invalid arguments
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCANNER="$SKILL_DIR/src/sin_codocs/scanner.py"

REPO_PATH="."
JSON=0
QUIET=0
KIND_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --json)        JSON=1 ;;
    --quiet|-q)    QUIET=1 ;;
    --kind=*)      KIND_ARGS+=("$arg") ;;
    --help|-h)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    -*) echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)  REPO_PATH="$arg" ;;
  esac
done

[[ -d "$REPO_PATH" ]] || { echo "Not a directory: $REPO_PATH" >&2; exit 1; }
REPO_PATH="$(cd "$REPO_PATH" && pwd)"
[[ -f "$SCANNER" ]] || { echo "Scanner missing: $SCANNER" >&2; exit 1; }

ARGS=(--path "$REPO_PATH")
[[ $JSON    -eq 1 ]] && ARGS+=("--json")
[[ ${#KIND_ARGS[@]} -gt 0 ]] && ARGS+=("${KIND_ARGS[@]}")

if [[ $JSON -eq 1 ]]; then
  python3 "$SCANNER" "${ARGS[@]}"
  exit $?
fi

# Human mode: run the scanner with --json, then format with the reporter
TMP="$(mktemp -t sin-codocs-sprint-scan.XXXXXX.json)"
trap 'rm -f "$TMP"' EXIT
python3 "$SCANNER" --path "$REPO_PATH" --json > "$TMP"

# Pass the lib path as $1 because __file__ in a heredoc is /dev/stdin
LIB_DIR="$SKILL_DIR/lib"
python3 - "$TMP" "$QUIET" "$LIB_DIR" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])  # the lib dir passed by the shell
from reporter import format_gap_table, format_gap_listing
from scanner import ScanResult

raw = json.loads(Path(sys.argv[1]).read_text())
sr = ScanResult(repo_path=raw["repo_path"],
                scanned_count=raw["scanned_count"],
                by_kind=raw["by_kind"])
for g in raw["gaps"]:
    # Recreate a Gap-shaped namespace so format_gap_listing works
    class _G: pass
    gg = _G()
    gg.kind = g["kind"]
    gg.rel_path = g["rel_path"]
    gg.detail = g["detail"]
    sr.gaps.append(gg)

print(f"\nCoDocs gap scan: {sr.repo_path}")
print(format_gap_table(sr))
if sys.argv[2] != "1":
    print(format_gap_listing(sr))
PY
