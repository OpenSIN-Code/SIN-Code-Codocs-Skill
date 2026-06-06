# sin-codocs/src/sin_codocs/repair_codocs.py

**Purpose:** Repair CoDocs references in a directory. Two repair modes
(idempotent, safe to re-run):

1. **MISSING-COMPANION**: code file declares `Docs: x.doc.md` but the
   referenced file does not exist → create a draft skeleton.
2. **WRONG-HEADER-PATH**: code file declares `Docs: <subdir>/x.doc.md`
   but the file lives at the parent directory (i.e. the header has
   an extra path component) → rewrite the header to the correct
   relative path.

**Source file:** `src/sin_codocs/repair_codocs.py` (Python)

**Header excerpt:**

```python
#!/usr/bin/env python3
"""Repair CoDocs references in a directory.

Two repair modes (idempotent, safe to re-run):
  1. MISSING-COMPANION: code file declares `Docs: x.doc.md` but the
     referenced file does not exist -> create a draft skeleton.
  2. WRONG-HEADER-PATH: code file declares `Docs: <subdir>/x.doc.md`
     but the file lives at the parent directory (i.e. the header has
     an extra path component) -> rewrite the header to the correct
     relative path.
"""
```

---

## What it does

Walks a source tree, parses `Docs:` references from the first 5
lines of every code file, and either creates missing companion
files or fixes broken relative paths in-place.

## Dependency map

- Imports from: stdlib only (`argparse`, `pathlib`, `re`, `sys`)
- Imported by: `sin-codocs repair <path>` CLI subcommand

## Important config

| Constant | Value | Why |
|---|---|---|
| `HEAD_LINES` | 5 | Mirror of `sin_codocs.codocs._HEAD_LINES` |
| `CODE_SUFFIXES` | 33 extensions | Same set as the upstream scanner |
| `EXCLUDE` | 12 dir basenames | Skip `.git`, `__pycache__`, `node_modules`, etc. |
| `SKELETON_TEMPLATE` | 30 lines | Standard draft .doc.md layout |

## Why these decisions

- **Idempotent**: running twice produces the same result. Skips files
  that already have a working companion or correct header.
- **No external deps**: stays stdlib-only so it can run in CI without
  `pip install`.
- **Heuristic path correction**: tries stripping leading subdir
  components and replacing the leading subdir with the file's
  parent dir name. This catches the common bug "Docs: scripts/foo.doc.md"
  in `scripts/foo.sh` (should be `foo.doc.md`).

## Usage example

```bash
# Dry-run (default, prints plan)
python3 -m sin_codocs.repair_codocs /path/to/repo

# Apply repairs
python3 -m sin_codocs.repair_codocs /path/to/repo --no-dry-run  # (currently always applies)
```

## Known caveats

- **Path correction is heuristic**: the algorithm tries 4 candidate
  paths. If none match an existing file, it falls back to creating
  a skeleton at the declared path. The dry-run output shows what
  was done so a human can verify.
- **Header in-place edits**: line rewrites preserve the rest of the
  file. The function reads + writes only the affected line.
- **No git integration**: doesn't auto-commit. The CI workflow at
  `.github/workflows/codocs.yml` runs the dry-run and fails the
  build if any fixes are needed.
