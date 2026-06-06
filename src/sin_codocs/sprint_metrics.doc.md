# metrics.py

**Purpose:** Sprint-specific coverage wrapper around sin-codocs metrics.

**Docs:** metrics.doc.md (this file)

## What it does

This is **not** a re-implementation of the CoDocs coverage math. It
subprocesses the upstream `sin-codocs/lib/metrics.py` (the single
source of truth) and adds sprint-only fields on top:

| Field | Source |
|---|---|
| `source_files`, `with_doc_md`, `overall_pct`, … | upstream verbatim |
| `sprint_files_remaining` | `source_files - with_doc_md` |
| `sprint_header_remaining` | `source_files - with_purpose_header` |
| `sprint_runtime_seconds` | wall-clock of the subprocess |
| `sprint_error` | non-empty when upstream failed |

## Dependencies

- **Imports from** (stdlib only):
  - `json`, `subprocess`, `sys`, `time` — stdlib
  - `dataclasses.asdict` — stdlib
  - `pathlib.Path` — stdlib
- **Imported by**:
  - `scripts/status.sh` — prints human coverage
  - `scripts/scan.sh` — produces JSON for the report
  - `scripts/sprint.sh` — runs scan, then generates
  - `scripts/diff.sh` — compares before/after
  - `tests/test_metrics.py` — unit tests

## Important config

- `SINCODOCS_METRICS` — absolute path to the upstream metrics lib.
  Defaults to `~/.config/opencode/skills/sin-codocs/lib/metrics.py`.
  Override by setting the env var if your install lives elsewhere.

## Usage examples

```python
from metrics import run_sprint_metrics

report = run_sprint_metrics("/path/to/repo")
print(f"Overall: {report.overall_pct:.1f}%")
print(f"Files still missing .doc.md: {report.sprint_files_remaining}")
```

CLI:

```bash
python3 lib/metrics.py --path /path/to/repo --json
```

## Design decisions

- **Subprocess, not import** — we want a clean process boundary so
  the upstream skill can be updated without forcing us to track its
  internal API surface. One env var, one file path.
- **No math re-implementation** — the CoDocs coverage formula lives
  in one place (sin-codocs). Anything else risks drift.
- **Sprint fields are derived** — `files_remaining` is just subtraction.
  If the upstream definition of "with .doc.md" ever changes, ours
  inherits the new definition automatically.

## Known caveats

- If the upstream path doesn't exist, `sprint_error` is set and
  everything else defaults to 0. Sprint tooling fails closed, not
  open — a missing upstream produces a visible error, never a
  silently-wrong coverage number.
- 300s timeout covers repos of ~50k source files. Larger monorepos
  should chunk the scan with `--path` on subtrees.

## Related

- `../lib/scanner.py` — finds the per-file gaps this lib aggregates
- `../lib/generator.py` — closes the gaps the scanner found
- `../../sin-codocs/lib/metrics.py` — the upstream coverage source
