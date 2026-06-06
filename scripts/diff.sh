#!/usr/bin/env bash
# Purpose: Show what would change before running a sprint (dry-run).
# Docs: ../SKILL.md
#
# Runs scan.sh against a repo, then for each MISSING_COMPANION gap
# prints what `generate.sh` would do. The repo is not modified.
#
# Usage:
#   diff.sh [REPO_PATH] [--json]
#
# Exit codes:
#   0  diff produced (gaps or not)
#   1  repo path not found
#   2  invalid arguments
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCANNER="$SKILL_DIR/src/sin_codocs/scanner.py"
GENERATOR="$SKILL_DIR/src/sin_codocs/generator.py"

REPO_PATH="."
JSON=0

for arg in "$@"; do
  case "$arg" in
    --json)  JSON=1 ;;
    --help|-h) sed -n '2,12p' "$0"; exit 0 ;;
    -*) echo "Unknown flag: $arg" >&2; exit 2 ;;
    *)  REPO_PATH="$arg" ;;
  esac
done

[[ -d "$REPO_PATH" ]] || { echo "Not a directory: $REPO_PATH" >&2; exit 1; }
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

TMP="$(mktemp -t sin-codocs-sprint-diff.XXXXXX.json)"
trap 'rm -f "$TMP"' EXIT
python3 "$SCANNER" --path "$REPO_PATH" --json > "$TMP"

if [[ $JSON -eq 1 ]]; then
  # Pure JSON: scanner output + a `planned_actions` array
  python3 - "$TMP" "$REPO_PATH" <<'PY'
import json, sys
from pathlib import Path
raw = json.loads(Path(sys.argv[1]).read_text())
repo = sys.argv[2]
actions = []
for g in raw["gaps"]:
    if g["kind"] != "MISSING_COMPANION":
        continue
    src = Path(repo) / g["rel_path"]
    doc = src.with_name(src.stem + ".doc.md")
    actions.append({"action": "create", "source": g["rel_path"],
                    "doc": str(doc.relative_to(repo))})
raw["planned_actions"] = actions
raw["files_to_create"] = len(actions)
print(json.dumps(raw, indent=2))
PY
  exit $?
fi

# Human mode
LIB_DIR="$SKILL_DIR/src/sin_codocs"
python3 - "$TMP" "$REPO_PATH" "$LIB_DIR" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from reporter import format_gap_table
from scanner import ScanResult

raw = json.loads(Path(sys.argv[1]).read_text())
sr = ScanResult(repo_path=raw["repo_path"],
                scanned_count=raw["scanned_count"],
                by_kind=raw["by_kind"])

print(f"\n=== CoDocs sprint dry-run: {sr.repo_path} ===")
print(format_gap_table(sr))

companion_gaps = [g for g in raw["gaps"] if g["kind"] == "MISSING_COMPANION"]
if not companion_gaps:
    print("\nNothing to create — all source files already have a .doc.md.")
else:
    print(f"\nWould create {len(companion_gaps)} .doc.md drafts:")
    repo = sys.argv[2]
    for g in companion_gaps[:50]:
        src = Path(repo) / g["rel_path"]
        doc = src.with_name(src.stem + ".doc.md")
        print(f"  + {g['rel_path']}  →  {doc.name}")
    if len(companion_gaps) > 50:
        print(f"  … and {len(companion_gaps) - 50} more")

print("\nRun `bash scripts/sprint.sh " + sr.repo_path + " --auto` to apply.")
PY
