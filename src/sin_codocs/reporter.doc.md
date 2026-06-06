# reporter.py

**Purpose:** Format scanner / metrics output as human-readable text.

**Docs:** reporter.doc.md (this file)

## What it does

Pure formatting library — no I/O, no subprocess, no mutation. Takes
structured data from `scanner.py` and `metrics.py` and renders it
for humans, CI logs, or commit messages.

| Function | Input | Output | Used by |
|---|---|---|---|
| `format_gap_table` | `ScanResult` | One-line-per-kind table | `scan.sh`, `sprint.sh` |
| `format_gap_listing` | `ScanResult` | Per-file bullet list | `sprint.sh --auto` preview |
| `format_sprint_summary` | `SprintReport` | Combined coverage + gap | `status.sh`, `sprint.sh` end |
| `format_diff` | two `SprintReport`s | Before/after delta | `diff.sh`, commit messages |

## Dependencies

- **Imports from**:
  - stdlib only: `argparse`, `json`, `pathlib`, `sys`, `typing`
- **Imported by**:
  - `scripts/scan.sh` (gap table)
  - `scripts/status.sh` (sprint summary)
  - `scripts/sprint.sh` (table + summary at end)
  - `scripts/diff.sh` (before/after)
  - `tests/test_reporter.py` (unit tests)

## Important config

None — this module is pure functions. The caller passes data in and
gets a string back.

## Usage examples

```python
from reporter import format_gap_table, format_sprint_summary
from scanner import scan_repo
from metrics import run_sprint_metrics

result = scan_repo("/repo")
print(format_gap_table(result))

sprint = run_sprint_metrics("/repo")
print(format_sprint_summary(sprint))
```

CLI:

```bash
# Pretty-print a saved scanner JSON
python3 lib/reporter.py --scanner-json /tmp/scan.json --mode listing

# Pretty-print a saved metrics JSON
python3 lib/reporter.py --metrics-json /tmp/metrics.json

# Show before/after delta
python3 lib/reporter.py --before /tmp/before.json --after /tmp/after.json
```

## Design decisions

- **Pure functions, no I/O** — every function takes a value and
  returns a string. The caller decides where the output goes. This
  makes the module trivially testable and reusable from a commit
  hook, a CI log, or a PR comment.
- **One function per output mode** — `format_gap_table` is not a
  parameter to `format_gap_listing`. They have different shapes and
  different consumers, and conflating them creates awkward flags.
- **Capped listing** — `format_gap_listing(max_lines=200)` keeps
  the output bounded. A repo with 10k gaps produces 200 lines plus
  a "… and N more" footer, not 10k lines of noise.

## Known caveats

- The CLI reconstructs lightweight `G` types from JSON, so the
  Gap-shape produced by `--scanner-json` is close to but not
  exactly the same as a real `Gap` dataclass. Sufficient for
  rendering, not for re-scanning.
- `format_diff` expects both inputs to be `SprintReport` of the
  same repo. Mismatched paths produce misleading deltas.

## Related

- `../lib/scanner.py` — produces the `ScanResult`
- `../lib/metrics.py` — produces the `SprintReport`
- `../lib/generator.py` — closes the gaps the reporter shows
- `../scripts/sprint.sh` — the main user of all four formatters
