# scanner.py

**Purpose:** Find per-file CoDocs gaps in a repo (read-only scanner).

**Docs:** scanner.doc.md (this file)

## What it does

Walks a directory tree and emits a structured list of every CoDocs
gap. Three kinds are detected:

| Kind | What it means | Example |
|---|---|---|
| `MISSING_COMPANION` | Source file has no `.doc.md` sibling | `auth.py` exists, `auth.doc.md` does not |
| `MISSING_HEADER` | First 10 lines lack a `Purpose:` + `Docs:` marker | — |
| `MISSING_DOCSTRING` | Public Python function has no docstring | `def verify_token(...)` without `"""..."""` |

The scanner is **read-only**. It never writes files. Generation is
a separate step (`lib/generator.py`).

## Dependencies

- **Imports from** (stdlib only):
  - `ast`, `re`, `dataclasses`, `pathlib`
- **Imported by**:
  - `scripts/scan.sh` — runs the scanner
  - `scripts/sprint.sh` — scan → generate
  - `scripts/diff.sh` — before/after comparison
  - `lib/reporter.py` — formats the ScanResult
  - `lib/generator.py` — closes the gaps the scanner found
  - `tests/test_scanner.py` — unit tests

## Important config

- `SOURCE_EXTS` — extensions the scanner counts as source code.
  Mirror of `sin-codocs/lib/metrics.py`. Keep in sync.
- `SKIP_DIRS` — directories never descended into
  (`node_modules`, `.venv`, `.sin-codocs-sprint`, …).
- `PURPOSE_RE` / `DOCS_RE` — regex for the header markers.
  Loose enough to match `# Purpose:`, `// Purpose:`, `Purpose:`,
  but strict enough not to match every line that happens to contain
  the word "purpose".

## Usage examples

```python
from scanner import scan_repo

result = scan_repo("/path/to/repo")
print(f"Files scanned: {result.scanned_count}")
for kind, n in result.by_kind.items():
    print(f"  {kind}: {n}")
```

CLI:

```bash
python3 lib/scanner.py --path /path/to/repo --json
python3 lib/scanner.py --path src/ --kind MISSING_COMPANION
```

## Design decisions

- **Read-only by contract** — generation lives in `generator.py`.
  Keeping the boundary clean means the scanner is safe to run in
  CI / pre-commit without surprising the developer.
- **Public functions, not all functions** — `_*` and `__*__` are
  skipped. Private functions rarely have a docstring by convention
  in Python and forcing them would generate noise.
- **AST for Python, regex for headers** — AST survives comments in
  strings, decorators, async. Regex is good enough for the header
  marker because the marker is line-based and short.
- **One pass, all gap kinds** — callers that want only
  `MISSING_COMPANION` can pass `--kind`, but the full scan is cheap
  (no I/O beyond `read_text`).

## Known caveats

- Docstring check is Python-only. TypeScript / Go / Rust are
  considered "complete" for the docstring axis. (A separate
  per-language checker is out of scope for the sprint tool.)
- The "header" check is keyword-based. A file whose first 10 lines
  mention `Purpose:` in a comment string will pass. We accept the
  false-positive rate because the alternative is a much heavier
  AST-based header detection that does not generalize to non-Python.
- A `.py` file with no public functions and no `.doc.md` will
  generate exactly 2 gaps (companion + header), no docstring gap.
  That is the expected count for a 0-LOC or module-only file.

## Related

- `../lib/generator.py` — closes the gaps this scanner finds
- `../lib/reporter.py` — formats `ScanResult` for humans
- `../lib/metrics.py` — aggregate coverage (separate axis)
- `../../sin-codocs/lib/metrics.py` — upstream coverage source
