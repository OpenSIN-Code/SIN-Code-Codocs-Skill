# sin-codocs

**SIN CoDocs — Co-located docs standard + sprint executor (merged skill).**

A unified tool for documenting code with the CoDocs standard: every
code file gets a `.doc.md` companion plus proper inline `#` comments.

## Two layers in one tool

| Layer | Purpose | Subcommands |
|---|---|---|
| **Validator** (read-only, stdlib-only) | Verify, audit, list | `check`, `check-inline`, `list`, `coverage`, `new-doc-md`, `new-module`, `init` |
| **Executor** (filesystem writes) | Bulk operations | `sprint`, `scan`, `generate`, `diff`, `status`, `install-skill` |

## Quick start

```bash
# Install
pip install -e .

# Verify all .doc.md companions resolve
sin-codocs check .

# Bulk-create missing .doc.md drafts (preview)
sin-codocs sprint . --auto --dry-run

# Apply + commit
sin-codocs sprint . --auto --commit
```

## Why one skill (not two)

This package is the merger of the previous `sin-codocs` (Standard)
and `sin-codocs-sprint` (Executor) skills. See [SKILL.md](SKILL.md)
for the full rationale.

The two-layer architecture is preserved — every previous command
still works, just under the unified `sin-codocs` binary:

```bash
# Old (separate skills, deprecated)
sin codocs check .            # was in sin-codocs
bash sprint.sh . --auto       # was in sin-codocs-sprint

# New (merged, recommended)
sin-codocs check .            # validator
sin-codocs sprint . --auto    # executor
```

## Documentation

- [SKILL.md](SKILL.md) — full skill description (for agent consumption)
- [docs/](docs/) — design docs, ADRs
- [templates/](templates/) — all .doc.md / inline-header templates
- [examples/](examples/) — good vs bad module examples

## Testing

```bash
pip install -e .[dev]
pytest tests/ -v
```

## License

MIT — see [LICENSE](LICENSE).

## Version

1.0.0 — first merged release.
