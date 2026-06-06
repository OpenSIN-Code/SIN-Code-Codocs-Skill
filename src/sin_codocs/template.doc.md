# template.py

**Purpose:** Canonical SOTA Python module skeleton.

**Docs:** template.doc.md (this file)

## What it does

This is the "skeleton" file used by `scripts/new-module.sh` to render a
new Python module. It demonstrates every rule in SKILL.md so it serves
as a runnable, self-checking example of the two-layer doc pattern.

If you copy this file, you will have a working module with:

- Module-level docstring containing `Purpose:` and `Docs:` keywords
- Section separators (`# ── Name ────...`)
- Public functions with full Google-style docstrings
- Internal helpers marked with a leading underscore
- Inline comments explaining magic values and non-obvious choices
- An `if __name__ == "__main__":` block for CLI / smoke-test use

## Dependencies

- **Imports from**:
  - `json` — stdlib, serialise config
  - `logging` — stdlib, structured log output
  - `os` — stdlib, read env vars
  - `pathlib.Path` — stdlib, file paths
  - `typing.Any` — stdlib, type hints
  - `yaml` — third-party, parse YAML config
- **Imported by**:
  - `scripts/new-module.sh` (renders this template)

## Important config

- `DEFAULT_TIMEOUT = 30` seconds; matches upstream SLA window
- `MAX_RETRIES = 3`; upstream guarantees < 2 failures per 1000
- `CONFIG_PATH` — read from `$APP_CONFIG` env var, defaults to `config.yaml`

## Usage examples

```python
from mypackage.lib.template import load_config

cfg = load_config()
print(cfg["name"], cfg["version"])
```

## Design decisions

- **Why `yaml.safe_load`**: arbitrary object construction is an RCE risk
- **Why exponential backoff**: gives upstream time to recover between tries
- **Why leading-underscore helpers**: signals "not part of public API"

## Known caveats

- `retry_with_backoff` does not check idempotency — do not use it for
  side-effect calls (payments, emails). Use an idempotency key.
- `load_config` requires `name` and `version` top-level keys; extend
  the `required` set if your config has more.
