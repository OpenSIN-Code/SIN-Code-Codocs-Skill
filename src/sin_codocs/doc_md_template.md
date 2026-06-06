# <filename.py>

**Purpose:** <one-line description of what this file does>

**Docs:** <this-file>.doc.md (this file)

## What it does

<1 paragraph — the elevator pitch. What is this file responsible for?
What would break if it were deleted?>

## Dependencies

- **Imports from** (look at the top of the source file):
  - `<module.a>` — <what it gives us>
  - `<module.b>` — <what it gives us>
- **Imported by** (find callers with `git grep "import <this>"`):
  - `<module.c>` — <how it uses us>
  - `<module.d>` — <how it uses us>

## Important config

- `<CONSTANT_NAME>` — <what controls, what range is safe>
- `<timeout>` — <units, why this value>

## Usage examples

Minimal end-to-end example. The reader should be able to copy-paste this.

```python
from <package> import <thing>

result = <thing>(arg="value")
print(result)
```

## Design decisions

- **Why X and not Y**: <one-line rationale for the non-obvious choice>
- **Why this layering**: <one-line on the module's place in the architecture>

## Known caveats

- <footgun 1 — what could go wrong, how to avoid it>
- <footgun 2 — edge case the code handles, but you should know>
- <DEPRECATED APIs> — when something is being phased out

## Related

- See `<sibling.doc.md>` for the related module
- See `<architecture.doc.md>` for the system-level view
