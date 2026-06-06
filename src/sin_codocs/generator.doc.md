# generator.py

**Purpose:** Auto-generate draft `.doc.md` files from source code.

**Docs:** generator.doc.md (this file)

## What it does

Given a source file, render a draft `.doc.md` companion pre-filled
with everything a tool can know automatically. A human still has to
fill in the WHY content.

```
┌────────────────────────────────────────────────────────────────┐
│ Source file (auth.py)                                          │
└────────────────────────────────────────────────────────────────┘
        │
        │  extract_facts()  →  imports, public_funcs, constants,
        │                      purpose, header excerpt
        ▼
┌────────────────────────────────────────────────────────────────┐
│ SourceFacts                                                    │
└────────────────────────────────────────────────────────────────┘
        │
        │  generate_draft()  →  template.format(...)
        ▼
┌────────────────────────────────────────────────────────────────┐
│ Draft .doc.md text  (write_draft() persists it)                │
└────────────────────────────────────────────────────────────────┘
        │
        │  human fills in the TODOs
        ▼
┌────────────────────────────────────────────────────────────────┐
│ Final .doc.md  (ship)                                          │
└────────────────────────────────────────────────────────────────┘
```

## Dependencies

- **Imports from** (stdlib only):
  - `ast`, `re`, `dataclasses`, `pathlib`
- **Imported by**:
  - `scripts/generate.sh` — single-file CLI
  - `scripts/sprint.sh` — bulk generation
  - `tests/test_generator.py` — unit tests

## Important config

- `TEMPLATE_PATH` — path to the bundled template
  (`templates/draft_template.md`). Resolved relative to this file.
- `write_draft(overwrite=False)` — refuses to clobber an existing
  `.doc.md`. Pass `overwrite=True` to force.

## Usage examples

Single file:

```python
from generator import generate_draft
text = generate_draft(Path("src/foo.py"))
Path("src/foo.doc.md").write_text(text)
```

Single file via CLI:

```bash
python3 lib/generator.py src/foo.py
python3 lib/generator.py src/foo.py --stdout > src/foo.doc.md
```

Bulk via sprint:

```bash
bash scripts/sprint.sh /path/to/repo --auto
```

## Design decisions

- **AST for Python, regex for TS/JS** — Python is parsed, JS gets
  a cheap regex pass. JS support is best-effort; the goal is "good
  enough draft", not "perfect extraction".
- **`write_draft` is the only writer** — the rest of the
  generator is pure functions. The boundary makes the writer easy
  to gate behind `--overwrite`.
- **Auto-fills are clearly marked** — every auto-detected block is
  prefixed with `<auto-detected — verify and add WHY …>`. The human
  can grep these out and replace them with real content.
- **Reuse the bundled template** — one source of truth for the
  draft skeleton. Renaming a section is a one-file change.

## Known caveats

- TS/JS import detection is regex-based and misses destructured
  imports. The "auto-detected" prefix makes the partial coverage
  visible.
- The generator only handles a small set of language markers for
  "Purpose" detection: `# Purpose:`, `// Purpose:`, and the first
  line of a triple-quoted docstring. New languages need an entry
  in `_extract_purpose`.
- `write_draft` will silently overwrite a file if `overwrite=True`.
  Sprint scripts default to `overwrite=False`; the human review
  step happens in `git diff`.

## Related

- `../lib/scanner.py` — finds what needs generating
- `../lib/reporter.py` — formats the gap report
- `../templates/draft_template.md` — the template this module renders
- `../../sin-codocs/templates/module.doc.md.template` — upstream reference
