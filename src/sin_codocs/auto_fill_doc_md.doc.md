# sin-codocs/src/sin_codocs/auto_fill_doc_md.py

**Purpose:** Auto-generate missing `.doc.md` companions for code files
that already declare a `Docs:` header. Idempotent: skips files that
already have a companion. Single-file granularity (the bulk mode lives
in `scanner.py` + `generator.py`).

**Source file:** `src/sin_codocs/auto_fill_doc_md.py` (Python)

**Header excerpt:**

```python
#!/usr/bin/env python3
"""Auto-generate missing .doc.md companions for code files that
already declare a `Docs:` header. Idempotent: skips files that
already have a companion. Designed to be called once per skill."""
```

---

## What it does

Walks a directory, finds every code file that has a `Docs:` header
in the first 5 lines, and creates a draft `.doc.md` skeleton next to
each source file whose referenced companion does not exist.

## Dependency map

- Imports from: stdlib only (`pathlib`, `re`, `sys`)
- Imported by: `sin-codocs auto-fill <path>` (planned CLI subcommand)
- Sister module: `repair_codocs.py` (also does path correction)

## Important config

| Constant | Value | Why |
|---|---|---|
| `HEAD_LINES` | 5 | Same as `sin_codocs.codocs._HEAD_LINES` |
| `CODE_SUFFIXES` | 33 extensions | Same set as the upstream scanner |
| `SKELETON_TEMPLATE` | 30 lines | Standard draft layout |

## Why these decisions

- **stdlib-only**: can run in CI without `pip install`
- **Single-file granularity**: the bulk operation belongs in
  `scanner.py` + `generator.py`; this module is the focused
  one-file-at-a-time mode.
- **Idempotent**: re-running produces the same result. Useful for
  CI gates that check "all code files have companions".

## Usage example

```python
from sin_codocs.auto_fill_doc_md import main
main(["/path/to/skill"])
```

## Known caveats

- **No header correction**: this module only creates missing
  companions. For path correction, use `repair_codocs.py`.
- **Skeleton is generic**: every generated companion is the same
  template; filling in real content is the human reviewer's job.
