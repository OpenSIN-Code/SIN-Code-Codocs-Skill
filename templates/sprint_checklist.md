<!--
  Template: sprint_checklist.md
  Purpose: Print/display the post-sprint checklist
  Docs: ../SKILL.md (Step 4 — commit)

  After `scripts/sprint.sh` runs, the human reviewer opens the new
  .doc.md files and works through this list. The skill outputs this
  checklist to the terminal at the end of every sprint run.
-->

# Post-sprint checklist (per file)

For every `.doc.md` the sprint just created, open the new doc and
walk through these 7 steps. Most take 30-90 seconds. The whole
sprint typically pays back in < 1 file per minute.

## 1. Confirm the Purpose line

```bash
head -10 path/to/file.doc.md
```

The `**Purpose:**` field at the top should be a 1-sentence
description that fits on one line. If the auto-detected purpose
came from a comment string, **replace it** with a real description
in your own words.

## 2. Fill in "What it does"

A single paragraph. Pretend you are writing for a teammate who
joined yesterday and has zero context on this codebase.

## 3. Verify the auto-detected imports

The `## Dependencies` block lists what the file imports. Each
entry should have a one-liner explaining WHAT it gives us. The
sprint left placeholders where it could not infer the WHY.

## 4. Add the design decisions

The `## Design decisions` section is the highest-value part of
the doc. Three to five bullets answering:

- Why this approach, not the obvious one?
- Why this layering / file location?
- What trade-off did we accept?

## 5. Add the usage example

The `## Usage examples` block should contain a copy-pasteable
5-10 line example. If a reader can `copy this block → run it →
see the expected output`, the doc passed its first test.

## 6. Capture the caveats

Walk the source looking for:

- `# not using X because Y` comments (the existing WHY)
- Deprecated functions (use the `# DEPRECATED(v2):` marker)
- Magic numbers (move to named constants with comments)
- Edge cases handled by `if x is None: return default`

Each one becomes a bullet under `## Known caveats`.

## 7. Cross-link siblings

The `## Related` block at the bottom should link to the 2-3 most
closely related `.doc.md` files. Use `git grep "import <module>"`
to find the callers.

## Once all 7 are done

```bash
git add path/to/file.doc.md
git commit -m "docs(<module>): add .doc.md companion"
```

If you ran `sprint.sh --commit`, this is already done — just
review the resulting commit message and amend if needed.

## Bulk-finish tip

If the sprint generated 50 drafts, do them in **dependency order**:
start with the leaves (no other module imports them), then climb
up. The cross-linking step (#7) gets easier as you go.
