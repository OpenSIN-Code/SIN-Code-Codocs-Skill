# sin-codocs/scripts/auto-fill-doc-md.sh

**Purpose:** Non-interactive wrapper around `auto_fill_doc_md.py`.
Sets `EDITOR=":"` so the embedded editor invocation is a no-op,
making the script safe to run from CI.

**Source file:** `scripts/auto-fill-doc-md.sh` (Shell)

**Header excerpt:**

```bash
#!/usr/bin/env bash
# Purpose: Non-interactive wrapper around auto_fill_doc_md.py
# Docs: auto-fill-doc-md.sh.doc.md
set -euo pipefail
```

---

## What it does

Delegates to `python3 -m sin_codocs.auto_fill_doc_md <path>`. The
script is a thin shell wrapper to match the pattern of all other
sin-codocs scripts (everything is callable both as a Python module
and as a shell script).

## Dependency map

- Calls: `python3 -m sin_codocs.auto_fill_doc_md`
- Imported by: `sin-codocs auto-fill` (planned CLI subcommand)

## Important config

- `set -euo pipefail` — strict mode.
- The Python invocation runs in the same process tree as the
  surrounding CI job, so the same Python env applies.

## Why these decisions

- **Shell wrapper, not Python entry point**: matches the layered
  pattern (CLI → shell script → Python module) used by all other
  sin-codocs commands. Lets CI users invoke `bash auto-fill-doc-md.sh`
  without installing the Python package.

## Usage example

```bash
bash scripts/auto-fill-doc-md.sh /path/to/skill
```

## Known caveats

- **Same idempotency guarantee as the Python module**: re-running is
  safe. The script does not auto-commit.
