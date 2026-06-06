"""Purpose: Find per-file CoDocs gaps in a repo.

Docs: scanner.doc.md

Walks a directory tree and identifies the specific files that need
attention. The output is a structured list of gaps that the rest of
the sprint pipeline (reporter, generator) consumes.

Three gap types are detected:

  1. MISSING_COMPANION  — file has no .doc.md sibling
  2. MISSING_HEADER     — file lacks a Purpose/Docs line
  3. MISSING_DOCSTRING  — public function/method has no docstring

The scanner is read-only. It never writes files. The generator is
the only sprint component that produces output.

Usage:
  from scanner import scan_repo
  result = scan_repo("/path/to/repo")
  for gap in result.gaps:
      print(gap.kind, gap.path)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────
# Mirror sin-codocs/lib/metrics.py so we agree on what counts as a
# source file. Changing one without the other creates drift.
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb"}

# Same skip-list as the upstream metrics lib. Keep in sync.
SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "build", "dist", ".next", ".tox", ".mypy_cache", ".pytest_cache",
    "target", ".sin-codocs-sprint",  # our own state dir
}

# Marker the scanner looks for in the first ~10 lines. Loose enough to
# match `# Purpose:`, `// Purpose:`, `Purpose:`, but strict enough not
# to match every line that happens to contain the word "purpose".
PURPOSE_RE = re.compile(r"Purpose\s*:")
DOCS_RE = re.compile(r"Docs\s*:")

# How many lines from the top of a file we scan for the header marker.
# 10 is the upstream convention; too small misses multi-line header
# blocks, too large starts matching accidental in-file mentions.
HEADER_SCAN_LINES = 10


# ── Public data types ─────────────────────────────────────────────────
@dataclass
class Gap:
    """A single CoDocs coverage gap."""
    kind: str                       # MISSING_COMPANION | MISSING_HEADER | MISSING_DOCSTRING
    path: str                       # absolute path to source file
    rel_path: str                   # path relative to repo root
    detail: str = ""                # e.g. function name for MISSING_DOCSTRING
    suggested_doc: str = ""         # absolute path the .doc.md SHOULD live at


@dataclass
class ScanResult:
    """Aggregated scanner output for one repo path."""
    repo_path: str
    source_files: list[str] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    by_kind: dict[str, int] = field(default_factory=dict)
    scanned_count: int = 0
    error: str = ""

    def __post_init__(self):
        if not self.by_kind:
            self.by_kind = {"MISSING_COMPANION": 0,
                            "MISSING_HEADER": 0,
                            "MISSING_DOCSTRING": 0}

    @property
    def has_gaps(self) -> bool:
        """True if any gap kind count is > 0. False for a clean scan."""
        return any(self.by_kind.values())

    def add(self, gap: Gap) -> None:
        """Record one gap and bump its per-kind counter.

        Args:
            gap: The gap to record. Its `kind` is used as the
                counter key in `by_kind`.
        """
        self.gaps.append(gap)
        self.by_kind[gap.kind] = self.by_kind.get(gap.kind, 0) + 1


# ── Public API ─────────────────────────────────────────────────────────
def scan_repo(repo_path: str | Path) -> ScanResult:
    """Walk a directory and return every CoDocs gap.

    Args:
        repo_path: Directory to scan. Must exist.

    Returns:
        ScanResult with all gaps, per-kind counts, and the list of
        source files seen. The result's `error` field is set if the
        path does not exist; otherwise it is "".
    """
    repo = Path(repo_path).resolve()
    result = ScanResult(repo_path=str(repo))
    if not repo.exists():
        result.error = f"path does not exist: {repo}"
        return result
    if not repo.is_dir():
        result.error = f"not a directory: {repo}"
        return result

    for src in _iter_sources(repo):
        result.scanned_count += 1
        rel = str(src.relative_to(repo))
        result.source_files.append(rel)
        _check_file(src, repo, result)
    return result


# ── Internal helpers ───────────────────────────────────────────────────
def _iter_sources(root: Path):
    """Yield source files under root, skipping common junk directories."""
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in SOURCE_EXTS:
            yield p


def _check_file(src: Path, repo: Path, result: ScanResult) -> None:
    """Run all per-file gap checks against one source file."""
    rel = str(src.relative_to(repo))
    doc = src.with_name(src.stem + ".doc.md")

    if not doc.exists():
        result.add(Gap(
            kind="MISSING_COMPANION",
            path=str(src),
            rel_path=rel,
            suggested_doc=str(doc),
        ))

    if not _has_header(src):
        result.add(Gap(
            kind="MISSING_HEADER",
            path=str(src),
            rel_path=rel,
        ))

    # Docstring check is Python-only — AST is reliable there
    if src.suffix == ".py":
        for func_name, lineno in _missing_docstrings(src):
            result.add(Gap(
                kind="MISSING_DOCSTRING",
                path=str(src),
                rel_path=rel,
                detail=f"{func_name} (line {lineno})",
            ))


def _has_header(path: Path) -> bool:
    """Heuristic: first HEADER_SCAN_LINES contain both markers.

    A file "has a header" iff both Purpose: and Docs: appear in the
    first 10 lines. This is intentionally lenient — the alternative
    is AST-based header detection that does not generalize to
    non-Python.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        # Unreadable files don't have a header by definition
        return False
    # First 10 lines only — anything deeper is not a header
    head = "\n".join(text.splitlines()[:HEADER_SCAN_LINES])
    return bool(PURPOSE_RE.search(head) and DOCS_RE.search(head))


def _missing_docstrings(path: Path) -> list[tuple[str, int]]:
    """Return [(name, lineno), ...] for public functions without docstrings.

    Uses AST (not regex) so the check survives comments inside strings,
    multi-line signatures, decorators, and async definitions. Private
    functions (leading underscore) and dunder methods are skipped.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        # Unparseable Python → fall back to no docstring findings.
        # The metrics lib's generic counter still runs.
        return []

    missing: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            # Convention: `_foo` is private, `__foo__` is dunder
            continue
        if ast.get_docstring(node) is None:
            missing.append((node.name, node.lineno))
    return missing


# ── CLI ────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the scanner.

    Parses --path (required), --json, and repeatable --kind flags,
    runs `scan_repo`, and prints either a JSON payload or a human
    table to stdout. Returns 0 on success, 2 on bad args / missing
    path, 1 if the repo path was not found.
    """
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Scan a repo for CoDocs gaps (read-only)."
    )
    parser.add_argument("--path", required=True, help="repo path to scan")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--kind", action="append", default=[],
                        choices=("MISSING_COMPANION", "MISSING_HEADER", "MISSING_DOCSTRING"),
                        help="filter to only these kinds (repeatable)")
    args = parser.parse_args(argv)

    result = scan_repo(args.path)
    if result.error:
        print(f"ERROR: {result.error}", file=sys.stderr)
        return 2

    if args.json:
        payload = {
            "repo_path": result.repo_path,
            "scanned_count": result.scanned_count,
            "by_kind": result.by_kind,
            "gaps": [
                {"kind": g.kind, "rel_path": g.rel_path,
                 "detail": g.detail, "suggested_doc": g.suggested_doc}
                for g in result.gaps
                if not args.kind or g.kind in args.kind
            ],
        }
        json.dump(payload, sys.stdout, indent=2)
        print()
    else:
        _print_human(result, args.kind)

    return 0


def _print_human(result: ScanResult, kind_filter: list[str]) -> None:
    print(f"\nCoDocs gap scan: {result.repo_path}")
    print(f"  Source files scanned: {result.scanned_count}")
    print(f"  Gaps by kind:")
    for k, v in result.by_kind.items():
        marker = "→" if v > 0 else " "
        print(f"    {marker} {k:20s} {v}")
    print()
    for g in result.gaps:
        if kind_filter and g.kind not in kind_filter:
            continue
        detail = f" — {g.detail}" if g.detail else ""
        print(f"  [{g.kind}] {g.rel_path}{detail}")


if __name__ == "__main__":
    import sys
    sys.exit(main())
