"""Purpose: Auto-generate draft .doc.md files from source code.

Docs: generator.doc.md

Given a source file, produce a draft `.doc.md` companion pre-filled
with everything a tool can know automatically. A human must still
fill in the WHY content (description, design decisions, caveats).

The generator NEVER overwrites an existing .doc.md. It only creates
drafts for files that lack one. The sprint workflow is:

    scanner  →  generator  →  human fills in WHY  →  ship

What the generator auto-fills:

  - Title from the file name
  - "Purpose" from the file's first line / module docstring
  - "Dependencies" from the imports block
  - "Source file" breadcrumb
  - All template sections from `templates/draft_template.md`

What a human MUST fill in (left as TODO placeholders):

  - Detailed "What it does" paragraph
  - Why the design choices were made
  - Magic values and their rationale
  - Usage examples
  - Known caveats

Usage:
  from generator import generate_draft
  text = generate_draft(Path("src/foo.py"))
  Path("src/foo.doc.md").write_text(text)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

# Path to the bundled template. Resolved at import time so a relocated
# install doesn't break it.
SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_DIR / "templates" / "draft_template.md"


@dataclass
class SourceFacts:
    """Everything we can learn about a source file without a human."""
    filename: str
    purpose: str = ""                  # from header / first docstring line
    header_excerpt: str = ""            # first ~10 lines
    imports: list[str] = field(default_factory=list)
    public_funcs: list[str] = field(default_factory=list)
    constants: list[tuple[str, str]] = field(default_factory=list)  # (name, value)
    language: str = "Python"

    @property
    def summary(self) -> str:
        """One-line human summary of the extracted facts.

        Used by the CLI to print what the generator detected
        without showing the full draft. Format:
        `purpose: …, N imports, M public funcs, K constants`.
        """
        bits = []
        if self.purpose:
            bits.append(f"purpose: {self.purpose[:60]}")
        bits.append(f"{len(self.imports)} imports")
        bits.append(f"{len(self.public_funcs)} public funcs")
        bits.append(f"{len(self.constants)} constants")
        return ", ".join(bits)


# ── Public API ─────────────────────────────────────────────────────────
def generate_draft(
    source_path: str | Path,
    *,
    facts: SourceFacts | None = None,
) -> str:
    """Render a draft .doc.md for one source file.

    Args:
        source_path: Path to the source file. Must be readable.
            If `facts` is provided, this is only used to derive
            the file name; it does not need to exist on disk.
        facts: Optional pre-computed facts. If None, the generator
            parses the file. Pass a `SourceFacts` to skip the parse
            step (useful for tests).

    Returns:
        The full draft `.doc.md` text, ready to write to disk.
        Raises FileNotFoundError if `source_path` does not exist
        AND `facts` is not provided.
        Raises FileNotFoundError if the template is missing.
    """
    src = Path(source_path).resolve()
    if facts is None and not src.exists():
        raise FileNotFoundError(src)
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"template not found: {TEMPLATE_PATH}"
        )

    if facts is None:
        facts = extract_facts(src)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = template.format(
        FILENAME=facts.filename,
        PURPOSE=facts.purpose or "<TODO: 1-line purpose>",
        HEADER_EXCERPT=facts.header_excerpt.strip() or "<no header>",
        IMPORTS=_render_imports(facts),
        PUBLIC_FUNCS=_render_public_funcs(facts),
        CONSTANTS=_render_constants(facts),
        LANGUAGE=facts.language,
        DOC_COMPANION=facts.filename + ".doc.md",
    )
    return rendered


def extract_facts(source_path: Path) -> SourceFacts:
    """Inspect a source file and return all the auto-fillable facts.

    Pure function: no I/O beyond `read_text` on the source file.
    """
    src = Path(source_path)
    facts = SourceFacts(filename=src.name)

    try:
        text = src.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return facts

    facts.header_excerpt = "\n".join(text.splitlines()[:10])
    facts.purpose = _extract_purpose(facts.header_excerpt)

    if src.suffix == ".py":
        facts.language = "Python"
        _populate_python(text, facts)
    elif src.suffix in {".ts", ".tsx", ".js", ".jsx"}:
        facts.language = "TypeScript" if src.suffix in {".ts", ".tsx"} else "JavaScript"
        _populate_jsts(text, facts)
    elif src.suffix == ".go":
        facts.language = "Go"
    elif src.suffix == ".rs":
        facts.language = "Rust"
    else:
        facts.language = src.suffix.lstrip(".").upper() or "Unknown"

    return facts


def write_draft(
    source_path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Generate the draft and write it next to the source file.

    Args:
        source_path: Source file to draft a doc for.
        overwrite: If False (default), refuse to overwrite an
            existing .doc.md. If True, clobber it.

    Returns:
        The path the .doc.md was written to.

    Raises:
        FileExistsError: if the .doc.md already exists and overwrite is False.
        FileNotFoundError: if the source does not exist.
    """
    src = Path(source_path).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    doc = src.with_name(src.stem + ".doc.md")
    if doc.exists() and not overwrite:
        raise FileExistsError(
            f"refusing to overwrite: {doc} (pass overwrite=True to clobber)"
        )
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(generate_draft(src), encoding="utf-8")
    return doc


# ── Internal helpers ───────────────────────────────────────────────────
# These regexes are intentionally lenient. The goal is a "good enough
# first draft" — the human refines from there. Tightening them would
# generate more empty sections, not fewer.
_PURPOSE_LINE_RE = re.compile(
    r"Purpose\s*:\s*(?P<p>.+?)(?:\n|$)", re.IGNORECASE
)
_DOCSTRING_RE = re.compile(r'^\s*"""(?P<body>.*?)"""', re.DOTALL)
_GO_PURPOSE_RE = re.compile(r"//\s*Purpose\s*:\s*(?P<p>.+?)(?:\n|$)")
_JS_PURPOSE_RE = re.compile(r"//\s*Purpose\s*:\s*(?P<p>.+?)(?:\n|$)")

# How many public methods to show inline for a class entry in
# `public_funcs`. Capped to keep the auto-generated section scannable.
MAX_INLINE_METHODS = 3

# Max length of a constant value preview (chars). Anything longer
# gets truncated with a "…" marker in the rendered doc.
MAX_CONSTANT_PREVIEW = 50


def _extract_purpose(header_excerpt: str) -> str:
    """Pull the Purpose: line out of the file header, if any.

    Tries the Purpose: marker first (Python, Go, JS variants), then
    falls back to the first line of a triple-quoted docstring.
    Returns an empty string if neither is found.
    """
    for rx in (_PURPOSE_LINE_RE, _GO_PURPOSE_RE, _JS_PURPOSE_RE):
        m = rx.search(header_excerpt)
        if m:
            return m.group("p").strip()
    # No Purpose: line — try the first line of the docstring as fallback
    m = _DOCSTRING_RE.search(header_excerpt)
    if m:
        first = m.group("body").strip().splitlines()
        if first:
            return first[0].strip().rstrip(".")
    return ""


def _populate_python(text: str, facts: SourceFacts) -> None:
    """Populate imports / public_funcs / constants from a .py file.

    Imports are captured by regex (always runs). The public_funcs and
    constants passes use AST for reliability — they survive comments
    in strings, decorators, and async defs. If the file does not
    parse, we silently skip the AST passes and keep the regex-only
    imports.
    """
    # Imports — quick regex first, then AST if it parses
    for m in re.finditer(r"^(?:from\s+(\S+)\s+)?import\s+(.+)$", text, re.M):
        if m.group(1):
            facts.imports.append(f"from {m.group(1)} import {m.group(2)}")
        else:
            facts.imports.append(f"import {m.group(2)}")

    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Don't crash on invalid Python — the import pass above still ran
        return

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                # Skip private/dunder — they're an internal detail
                facts.public_funcs.append(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                # Document the class plus its first N public methods
                methods = [
                    c.name for c in node.body
                    if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not c.name.startswith("_")
                ]
                # Inline method list is capped for readability
                suffix = (f" (methods: {', '.join(methods[:MAX_INLINE_METHODS])})"
                          if methods else "")
                facts.public_funcs.append(f"{node.name}()" + suffix)
        elif isinstance(node, ast.Assign):
            # Module-level assignments to a single Name with a constant
            # value are treated as named constants and recorded.
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and isinstance(node.value, ast.Constant):
                    if isinstance(node.value.value, (int, float, str)):
                        facts.constants.append((tgt.id, repr(node.value.value)))


def _populate_jsts(text: str, facts: SourceFacts) -> None:
    """Populate imports / public_funcs / constants from a .ts/.js file.

    Best-effort regex pass. Does NOT handle:
      - Destructured imports (`import { x, y } from 'z'`)
      - Default exports of arrow functions
      - Re-exports / barrel files
    Those are accepted as known limitations; the human reviewer can
    add the missing entries by hand.
    """
    for m in re.finditer(
        r"^import\s+(?:.+?\s+from\s+)?['\"](?P<mod>[^'\"]+)['\"]", text, re.M
    ):
        facts.imports.append(m.group("mod"))

    for m in re.finditer(
        r"^export\s+(?:async\s+)?function\s+(?P<name>\w+)", text, re.M
    ):
        facts.public_funcs.append(m.group("name") + "()")

    for m in re.finditer(
        r"^export\s+class\s+(?P<name>\w+)", text, re.M
    ):
        facts.public_funcs.append(m.group("name") + "()")

    for m in re.finditer(
        r"^export\s+const\s+(?P<name>\w+)\s*=\s*(?P<val>[^;]+);", text, re.M
    ):
        # Truncate long RHS values to keep the rendered doc scannable
        facts.constants.append((m.group("name"),
                                m.group("val").strip()[:MAX_CONSTANT_PREVIEW]))


def _render_imports(facts: SourceFacts) -> str:
    if not facts.imports:
        return "<TODO: list what this file imports and what each one gives us>\n  - `<module.a>` — <what it gives us>\n  - `<module.b>` — <what it gives us>"
    head = "<auto-detected — verify and add WHY each is used>\n"
    body = "\n".join(f"  - `{imp}`" for imp in facts.imports[:20])
    if len(facts.imports) > 20:
        body += f"\n  - … and {len(facts.imports) - 20} more (truncated)"
    return head + body


def _render_public_funcs(facts: SourceFacts) -> str:
    if not facts.public_funcs:
        return "<no public functions detected>"
    head = "<auto-detected — add per-function WHY it exists>\n"
    body = "\n".join(f"- `{name}`" for name in facts.public_funcs)
    return head + body


def _render_constants(facts: SourceFacts) -> str:
    if not facts.constants:
        return "<TODO: list every named constant with the units and rationale>"
    head = "<auto-detected — each needs a WHY comment in the source too>\n"
    body = "\n".join(f"- `{name} = {value}`" for name, value in facts.constants)
    return head + body


# ── CLI ────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the generator.

    Parses the source path, --stdout, and --overwrite. Writes
    the draft to the .doc.md next to the source by default, or
    to stdout if --stdout is passed. Returns 0 on success, 1
    if the .doc.md already exists (without --overwrite), 2 on
    bad args / missing source.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Generate a draft .doc.md for a single source file."
    )
    parser.add_argument("source", help="path to source file")
    parser.add_argument("--stdout", action="store_true",
                        help="print to stdout instead of writing")
    parser.add_argument("--overwrite", action="store_true",
                        help="overwrite an existing .doc.md (dangerous)")
    args = parser.parse_args(argv)

    if args.stdout:
        sys.stdout.write(generate_draft(args.source))
        return 0
    try:
        path = write_draft(args.source, overwrite=args.overwrite)
    except FileExistsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"ERROR: source not found: {e}", file=sys.stderr)
        return 2
    print(f"Created: {path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
