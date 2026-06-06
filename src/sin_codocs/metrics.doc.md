# metrics.py

**Purpose:** Compute CoDocs coverage metrics for a repo.

**Docs:** metrics.doc.md (this file)

## What it does

Walks a directory tree and produces a `CoverageReport` with four metrics:

1. **`.doc.md` coverage** — what % of source files have a companion doc
2. **Header coverage** — what % have a `Purpose:`/`Docs:` line
3. **Docstring coverage** — what % of public functions have docstrings
4. **Comment density** — ratio of comment lines to total LOC

A weighted overall score (40/30/20/10) is used as the gate value.

## Dependencies

- **Imports from**:
  - `argparse`, `ast`, `json`, `sys` — stdlib
  - `dataclasses.asdict` — stdlib
  - `pathlib.Path` — stdlib
- **Imported by**:
  - `scripts/coverage.sh` (the bash wrapper)
  - `ceo-audit` skill's `axis_docs` gate

## Important config

- `SOURCE_EXTS` — extensions counted as source code
- `SKIP_DIRS` — directories never descended into (node_modules, .venv, …)
- Weighted overall: doc.md (40%) + header (30%) + docstring (20%) + density (10%)

## Usage examples

```python
from lib.metrics import measure

report = measure("/path/to/repo")
print(f"Overall coverage: {report.overall_pct:.1f}%")
```

CLI:

```bash
python3 lib/metrics.py --path src/ --json --min 70
```

## Design decisions

- **AST for Python, regex for others** — Python's AST survives comments
  inside strings, decorators, async code. Other languages get a rough
  LOC count which is "good enough" for trend tracking.
- **Skip common junk dirs** — `.venv`, `node_modules`, etc. would
  dominate the count and skew metrics.
- **Weighted overall** — doc.md coverage is the strongest signal that
  someone cared about the file; it gets the highest weight.

## Known caveats

- The "Purpose keyword" heuristic is line-based, not AST-based, so
  a `Purpose:` mention in a string literal will count as a hit.
- Comment density caps at 30% — files with > 30% comment lines get
  capped before being folded into the overall score.
