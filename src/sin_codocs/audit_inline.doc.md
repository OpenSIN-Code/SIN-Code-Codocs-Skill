# audit_inline.py

**Purpose:** AST-based audit of inline comment quality for Python files.

**Docs:** audit_inline.doc.md (this file)

## What it does

Walks a Python source file's AST and reports:

- Module docstring presence + Purpose/Docs keywords
- Public function/method docstring coverage
- Magic-number density (constants without inline context)
- Cyclomatic-ish complexity per function

Used as a pre-commit gate and by the ceo-audit `axis_docs` checker.

## Dependencies

- **Imports from**:
  - `argparse`, `ast`, `json`, `sys` — stdlib
  - `dataclasses.dataclass`, `field` — stdlib
  - `pathlib.Path` — stdlib
- **Imported by**:
  - `scripts/check.sh` (indirectly, via audit hooks)
  - `ceo-audit` skill

## Important config

- Thresholds: complexity > 15 = warning, > 5 magic numbers = warning
- Magic numbers 0/1/-1/2 are not flagged (too common to be "magic")

## Usage examples

CLI:

```bash
python3 lib/audit_inline.py src/auth.py
python3 lib/audit_inline.py --json --strict src/
```

Library:

```python
from lib.audit_inline import audit_file

result = audit_file("src/auth.py")
print(f"Docstring coverage: {result.docstring_coverage * 100:.0f}%")
for issue in result.issues:
    print(f"  ! {issue}")
```

## Design decisions

- **AST-based, not regex** — survives comments inside strings, multi-line
  expressions, decorators, and async code. A regex audit would
  mis-report docstrings containing the word "Purpose" as Purpose headers.
- **Pure stdlib** — no external deps, so the audit runs even before the
  project's venv is set up. Critical for first-run setup.
- **Magic-number heuristic** is intentionally simple: it counts numeric
  literals in function bodies, subtracts the values of module-level
  numeric assignments. False positives are tolerable; we just want a
  signal to investigate.

## Known caveats

- Skips dunder methods (`__init__`, `__repr__`, etc.) when counting
  public functions — adjust if your codebase treats dunders as part
  of the public API.
- The complexity score is a rough proxy for cyclomatic complexity.
  For accurate numbers, use `radon` or `mccabe`.
