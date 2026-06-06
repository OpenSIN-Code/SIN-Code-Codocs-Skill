# Purpose: Unified SKILL.md for merged sin-codocs + sin-codocs-sprint
# Docs: SKILL.doc.md
"""
SIN CoDocs — Co-located docs standard + sprint executor (merged skill).

> ## ⚠️ MIGRATION — `sin-codocs-sprint` is DEPRECATED as of v1.0.0
>
> The previously separate `sin-codocs` and `sin-codocs-sprint` skills
> are now **one unified skill**: `sin-codocs`. The old
> `sin-codocs-sprint` repository is archived.
>
> **If your `opencode.json` still lists `sin-codocs-sprint` in
> `skills.baseline`:** remove it and add `sin-codocs` instead.
> See the [Migration](#migration-from-pre-v100) section below.
>
> **If you have a stale local checkout** at
> `~/.config/opencode/skills/sin-codocs-sprint/`, delete it — the
> canonical source is now
> [`OpenSIN-Code/SIN-Code-Codocs-Skill`](https://github.com/OpenSIN-Code/SIN-Code-Codocs-Skill)
> (the same repo that hosts `sin-codocs`).

## What this is

Two-layer tool for the OpenSIN-Code ecosystem:

  - **Validator (read-only, stdlib-only):**
    check, check-inline, list, coverage, new-doc-md, new-module, init
  - **Executor (read-write, filesystem):**
    sprint, scan, generate, diff, status, install-skill

The executor layer is a convenience wrapper OVER the validator. It
does not reimplement coverage math — it subprocesses the validator's
metrics and adds sprint-only metadata.

## When to use which

| Task | Use | Why |
|------|-----|-----|
| Verify all .doc.md companions resolve | `sin-codocs check .` | CI-gate, exit 1 on broken refs |
| Check Purpose/Docs headers + docstrings | `sin-codocs check-inline .` | Inline-doc quality gate |
| See coverage % in one line | `sin-codocs status .` | Quick health check |
| Bulk-create missing .doc.md drafts | `sin-codocs sprint . --auto` | Coverage sprint |
| Preview what sprint would change | `sin-codocs diff .` | Dry-run before bulk |
| Create ONE .doc.md (interactive editor) | `sin-codocs new-doc-md src/foo.py` | Single-file creation |
| Scaffold a NEW module with CoDocs | `sin-codocs new-module src/foo.py` | New project / new file |
| Bootstrap a repo with CoDocs | `sin-codocs init .` | First-time setup |
| Install the skill into opencode | `sin-codocs install-skill` | One-time install |

## Trigger phrases

The agent should load this skill when the user says:

- "document this" / "add docs" / "explain the code"
- "comment this" / "add inline documentation"
- "self-documenting code" / "SOTA docs"
- "CoDocs sprint" / "doc coverage sprint"
- "improve documentation" / "add docs to all files"
- "bring to 100% coverage" / "auto-generate .doc.md"
- "draft documentation"

## CLI examples

```bash
# Validator layer (read-only, safe in CI)
sin-codocs check .
sin-codocs check-inline . --json
sin-codocs coverage . --min 70
sin-codocs status .

# Executor layer (writes files, use with care)
sin-codocs new-doc-md src/auth.py
sin-codocs sprint . --auto --dry-run    # preview
sin-codocs sprint . --auto              # apply
sin-codocs sprint . --auto --commit     # apply + commit
```

## Architecture

```
sin_codocs/                       # This skill (1 repo)
├── src/sin_codocs/
│   ├── cli.py                    # Unified CLI entry point
│   ├── validator.py              # Read-only validators
│   ├── mutator.py                # Read-write mutators
│   ├── scanner.py                # Gap detection (sprint)
│   ├── generator.py              # .doc.md generation (sprint)
│   ├── reporter.py               # Coverage reports (sprint)
│   ├── template.py               # Doc templates
│   ├── audit_inline.py           # Inline doc checks
│   ├── metrics.py                # Single source of truth for coverage math
│   └── sprint_metrics.py         # Sprint-only metadata wrapper
├── scripts/                      # Shell entry points (CI-friendly)
│   ├── check.sh / coverage.sh / init.sh
│   ├── new-doc-md.sh / new-module.sh
│   └── sprint.sh / scan.sh / generate.sh / diff.sh / status.sh / install-skill.sh
├── templates/                    # All .doc.md / inline templates
├── tests/                        # 7 test modules
├── examples/good/ + bad/         # Anti-examples
└── docs/                         # This SKILL.md + .doc.md companions
```

## Why a single skill (not two)

This skill is the merger of two previous skills:

  - `sin-codocs` (Standard / Validator) — read-only, stdlib-only
  - `sin-codocs-sprint` (Executor) — bulk operations

The two were merged in v1.0.0 to:

  1. **Eliminate cross-skill duplication** (both had `metrics.py`,
     `check.sh`, `coverage.sh`, etc.)
  2. **Provide a single, discoverable CLI** (`sin-codocs check`,
     `sin-codocs sprint`) instead of two separate binaries
  3. **Reduce maintenance surface** from 2 repos to 1

The merge is structural, not functional — every previous command still
works, just under the unified `sin-codocs` binary.

## Migration from pre-v1.0.0

If you were using `sin-codocs` + `sin-codocs-sprint` as two separate
skills (v0.5.x or earlier), follow these steps to migrate:

### 1. Update `opencode.json` baseline

```diff
  "skills": {
    "baseline": [
-     "sin-codocs-sprint",
      "sin-codocs",
      ...
    ]
  }
```

### 2. Remove the old local checkout

```bash
rm -rf ~/.config/opencode/skills/sin-codocs-sprint
```

### 3. Re-clone the canonical source (only if your local sin-codocs
   is also stale)

```bash
rm -rf ~/.config/opencode/skills/sin-codocs
git clone https://github.com/OpenSIN-Code/SIN-Code-Codocs-Skill.git \
    ~/.config/opencode/skills/sin-codocs
```

### 4. Rewrite old commands

| Old (v0.5) | New (v1.0.0) |
|------------|--------------|
| `sin codocs check .` | `sin-codocs check .` |
| `bash sprint.sh . --auto` | `sin-codocs sprint . --auto` |
| `bash scan.sh .` | `sin-codocs scan .` |
| `bash generate.sh file.py` | `sin-codocs generate file.py` |
| `bash status.sh .` | `sin-codocs status .` |
| `bash diff.sh .` | `sin-codocs diff .` |
| `bash install-skill.sh` | `sin-codocs install-skill` |
| `bash new-doc-md.sh file.py` | `sin-codocs new-doc-md file.py` |
| `bash new-module.sh file.py` | `sin-codocs new-module file.py` |
| `bash init.sh .` | `sin-codocs init .` |
| `bash coverage.sh .` | `sin-codocs coverage .` |

### 5. Verify

```bash
sin-codocs --help              # should list 13 subcommands
sin-codocs check .             # should report no new issues introduced by the migration
pytest ~/.config/opencode/skills/sin-codocs/tests/ -v
```

Expected: 65/88 tests pass. The 23 failing tests are documented
migration debt — they reference the pre-merge `lib/` paths and will
be rewritten in v1.0.1 (see CHANGELOG.md).

## Related tools

- `sin-code-bundle` — the meta-CLI; bundles `sin-codocs` (and others)
  as a single install. `pip install sin-code-bundle` exposes the
  `sin codocs` namespace.
- `ceo-audit` — runs `sin-codocs check` as part of its 47 quality
  gates (the `axis_docs` gate).
- `git-immortal-commit` — pair with `sin-codocs sprint --commit` to
  make every sprint a permanent commit.

## Language-specific CoDocs conventions

**IMPORTANT:** The `# Purpose:` / `# Docs:` header syntax is **Python-only**.
For Go files, use `// Purpose:` and `// Docs:` (double-slash comments).

| Language | File header | Docstring style | Section separators |
|----------|-------------|-----------------|-------------------|
| Python   | `"""Purpose: ...\n\nDocs: ...\n"""` | `"""` triple-quote | `# ── Section ────` |
| Go       | `// Purpose: ...\n// Docs: ...` | `//` single-line | `// ── Section ────` |
| TypeScript/JS | `/** Purpose: ...` | `/** */` JSDoc | `// ── Section ────` |
| Rust     | `//! Purpose: ...` | `//!` outer doc | `// ── Section ────` |

**When creating new modules** via `sin-codocs new-module`:
- Python → uses `templates/module.py.template`
- Go → uses `templates/module.go.template`
- The validator (`sin-codocs check-inline`) knows both patterns and checks accordingly

**Common mistake:** Copying a Python `"""Purpose:"""` header into a `.go` file — this is a syntax error in Go. Always use the Go template for Go files.

## Testing

```bash
pip install -e .[dev]
pytest tests/ -v
```

All 7 test modules should pass.

## Version

1.0.0 — first merged release. See CHANGELOG.md for the full history.
"""
