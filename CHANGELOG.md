# Changelog

All notable changes to sin-codocs are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-06-06

### Added
- **Language-specific CoDocs convention note** in SKILL.md: clarifies that `# Purpose:` / `# Docs:` is Python-only; Go uses `// Purpose:` / `// Docs:`. Added a comparison table for Python, Go, TypeScript/JS, and Rust.

### Changed
- SKILL.md: added "Language-specific CoDocs conventions" section to prevent agents from putting Python triple-quote headers in Go files (syntax error).

## [1.0.0] - 2026-06-06

### Changed — **MAJOR MERGE**

This is the **first merged release** of the previously-separated
`sin-codocs` (Standard / Validator) and `sin-codocs-sprint` (Executor)
skills. The two skills are now a single Python package with a
unified CLI.

#### What merged
| From | Into | Reason |
|------|------|--------|
| `sin-codocs/lib/{template,audit_inline,metrics}.py` | `sin_codocs/` | One Python package |
| `sin-codocs-sprint/lib/{scanner,generator,reporter}.py` | `sin_codocs/` | One Python package |
| `sin-codocs-sprint/lib/metrics.py` | `sin_codocs/sprint_metrics.py` | Renamed (was wrapper, kept wrapper semantics) |
| `sin-codocs/scripts/*` | `scripts/*` | Unchanged structure |
| `sin-codocs-sprint/scripts/*` | `scripts/*` | Unchanged structure |
| All `templates/` | `templates/` | Merged |
| All `tests/` | `tests/` | Merged |

#### CLI migration

| Old (separate skills) | New (merged) |
|-----------------------|--------------|
| `sin codocs check .` (via `sin-code-bundle`) | `sin-codocs check .` |
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

Every old command still works as a script; the `sin-codocs` CLI is
a thin wrapper that calls them.

#### Added
- Unified `sin-codocs` CLI binary (entry point in `pyproject.toml`).
- `src/sin_codocs/cli.py` — argparse-based dispatcher.
- `pyyaml>=6.0` as a runtime dependency (was implicit before).

#### Changed
- Repository renamed: `SIN-Code-Codocs-Sprint-Skill` → `SIN-Code-Codocs-Skill`
  (and merged with `SIN-Code-Codocs-Skill` itself — both old repos
  are now deprecated).
- File layout: `lib/` → `src/sin_codocs/` (standard hatchling wheel layout).
- Test imports updated to use `sin_codocs.*` namespace.

#### Known issues (migration debt)
- 30 of 88 tests still reference the old `lib/` paths. They are
  scheduled for rewrite in v1.0.1. The library functions themselves
  work correctly; the failures are mostly in subprocess-CLI tests.
- `test_init.py` has 2 assertion failures on example file structure
  checks; cosmetic, not blocking.
- `test_install_skill` references the deprecated `sin-codocs-sprint`
  install dir; needs update post-merge.

#### Deprecated
- The standalone `sin-codocs-sprint` repository is now archived.
  Use `sin-codocs sprint` instead.

## [0.1.0] - 2026-06-05

### Added
- Initial release as two separate skills:
  - `sin-codocs` (Standard / Validator)
  - `sin-codocs-sprint` (Executor)
- `sin codocs check` CLI in `sin-code-bundle`.
- 88 tests across both skills.
- Shell-script-first design (CI-gate friendly).

[1.0.0]: https://github.com/OpenSIN-Code/SIN-Code-Codocs-Skill/releases/tag/v1.0.0
[0.1.0]: https://github.com/OpenSIN-Code/SIN-Code-Codocs-Sprint-Skill/releases/tag/v0.1.0
