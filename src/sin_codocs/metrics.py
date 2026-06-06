"""Purpose: Compute CoDocs coverage metrics for a repo.

Docs: metrics.doc.md

Computes four SOTA-doc health metrics for a target directory tree:

  1. .doc.md coverage   — % of source files with a .doc.md companion
  2. Header coverage    — % of source files with a Purpose/Docs header
  3. Docstring coverage — % of public functions with docstrings
  4. Comment density    — average ratio of comment lines to total LOC

Used by `scripts/coverage.sh` and by the ceo-audit `axis_docs` gate.

Usage:
  python3 metrics.py --path /repo --json --min 70
  python3 metrics.py --path src/

Exit codes:
  0  coverage >= --min
  1  coverage < --min
  2  invalid args
"""

# ─────────────────────────────────────────────────────────────────────────
# Design notes (architecture decisions, kept here so reviewers see them
# in-file rather than only in the .doc.md companion):
#
# • Why AST for Python, regex for everything else:
#   Python's ast module survives comments inside strings, decorators, and
#   async code; a regex would either over- or under-count. For other
#   languages we accept a rougher LOC measurement because the audience
#   for this metric is trend tracking, not audit-grade precision.
#
# • Why "Purpose:" in the first 10 lines:
#   File headers vary in length. Ten lines is long enough to cover the
#   most common module-docstring style ("""...""") and short enough
#   that it won't accidentally match a "Purpose:" mention deep in a
#   function body where it would be misleading.
#
# • Why we skip teaching dirs by default:
#   examples/ and tests/ in this skill intentionally violate the rules
#   to demonstrate what bad looks like. Counting them in a self-audit
#   would penalize the skill for its own teaching artifacts.
#   Callers can still point --path at examples/ explicitly to score
#   those demos (see TEACHING_DIRS below for the rule).
#
# • Why comment density caps at 30% in the overall formula:
#   Above ~30% comment ratio, the file is almost certainly a doc-heavy
#   template (e.g. this very file) rather than production code. Capping
#   prevents the metric from being gamed by adding LLM-style noise
#   comments to inflate the score.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Source extensions we audit (must match scripts/init.sh).
# .sh is intentionally excluded — shell scripts are tooling, not the
# source code being measured, and treating them as source would skew
# the LOC denominator with no corresponding .doc.md requirement.
SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb"}

# Directories we never descend into. Anything that would dominate the
# count with vendored / generated / VCS-internal files goes here.
SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "build", "dist", ".next", ".tox", ".mypy_cache", ".pytest_cache",
    "target",  # Rust
}

# Teaching/demonstration directories — skipped only when the scan root is OUTSIDE them.
# When you point the metric at examples/ directly we still want to score it
# (so test_metrics can verify the "bad" example scores low). But when scoring
# the skill itself, examples/ and tests/ are teaching artifacts and tooling,
# not source code that should carry a .doc.md companion.
TEACHING_DIRS = {"examples", "tests"}

# Cap for the comment-density contribution to the overall score.
# See the design-note block at the top of the file for the rationale.
COMMENT_DENSITY_CAP = 30.0

# Default gate threshold for the CLI; matches scripts/coverage.sh's default.
DEFAULT_MIN_PERCENT = 70


@dataclass
class CoverageReport:
    """Aggregate coverage metrics for a single repo path."""
    path: str
    source_files: int = 0
    with_doc_md: int = 0
    with_purpose_header: int = 0
    public_funcs: int = 0
    public_funcs_with_doc: int = 0
    total_loc: int = 0
    comment_loc: int = 0

    @property
    def doc_md_pct(self) -> float:
        """Percent of source files that have a `.doc.md` companion (0-100)."""
        return 100.0 * self.with_doc_md / self.source_files if self.source_files else 100.0

    @property
    def header_pct(self) -> float:
        """Percent of source files with a `Purpose:`/`Docs:` header (0-100)."""
        return 100.0 * self.with_purpose_header / self.source_files if self.source_files else 100.0

    @property
    def docstring_pct(self) -> float:
        """Percent of public functions whose first statement is a docstring (0-100)."""
        return 100.0 * self.public_funcs_with_doc / self.public_funcs if self.public_funcs else 100.0

    @property
    def comment_density_pct(self) -> float:
        """Ratio of comment lines to total LOC, expressed as a percent (0-100)."""
        return 100.0 * self.comment_loc / self.total_loc if self.total_loc else 0.0

    @property
    def overall_pct(self) -> float:
        """Weighted overall: doc.md (40%) + header (30%) + docstring (20%) + density (10%).

        Returns 0.0 when there are no source files (avoids NaN from the
        doc_md_pct / header_pct division-by-zero guards defaulting to 100).
        """
        if self.source_files == 0:
            return 0.0
        # Density is capped before being folded in (see COMMENT_DENSITY_CAP).
        density_slice = (
            min(self.comment_density_pct, COMMENT_DENSITY_CAP)
            / COMMENT_DENSITY_CAP
            * 100.0
            * 0.1
        )
        return (
            self.doc_md_pct * 0.4
            + self.header_pct * 0.3
            + self.docstring_pct * 0.2
            + density_slice
        )


# ── Public API ─────────────────────────────────────────────────────────
def measure(path: str | Path) -> CoverageReport:
    """Walk a directory tree and compute coverage metrics.

    Args:
        path: Root directory to scan. Recurses into subdirs.

    Returns:
        CoverageReport with per-metric counts and percentages.
    """
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(root)
    if root.is_file():
        sources = [root]
    else:
        sources = list(_iter_sources(root))

    report = CoverageReport(path=str(root.resolve()))
    for src in sources:
        report.source_files += 1
        if _has_companion_doc(src):
            report.with_doc_md += 1
        if _has_purpose_header(src):
            report.with_purpose_header += 1
        if src.suffix == ".py":
            _measure_python(src, report)
        else:
            _measure_generic(src, report)
    return report


def _has_companion_doc(src: Path) -> bool:
    """Check whether `src` has a matching `.doc.md` companion.

    For `auth.py`, looks for `auth.doc.md` (sibling, same stem).
    For `auth.py`, does NOT look for `auth.py.doc.md`.

    Implementation note: we use `with_suffix("")` twice instead of
    `with_stem` because `with_stem` was only added in Python 3.9, and
    some of our consumers (CI shims) still target 3.8. The double
    suffix-strip is a one-line cost for broader compatibility.
    """
    # Build the companion path: `auth.py` → `auth.doc.md` (same dir).
    # The `.with_suffix("")` is called twice because the FIRST call
    # drops the extension; we then add the `.doc.md` suffix back so
    # `with_name` sees the right stem.
    companion = src.with_suffix("") .with_name(src.with_suffix("").name + ".doc.md")
    # `exists()` returns False for broken symlinks, which is what we want
    # — a broken .doc.md link is the same as no companion for coverage
    # purposes.
    return companion.exists()


# ── Internal helpers ───────────────────────────────────────────────────
def _iter_sources(root: Path):
    """Yield source files under root, skipping common junk directories.

    The skip list is layered: SKIP_DIRS always wins (vendor/VCS dirs),
    and TEACHING_DIRS is only applied when the scan root is OUTSIDE
    them. See TEACHING_DIRS at the top of the file for the rationale.
    """
    # Determine if the scan root itself is a teaching dir. If it is, do NOT
    # apply the teaching-dir skip (the caller is intentionally scoring it).
    # Otherwise, treat examples/ and tests/ as out-of-scope when found below root.
    # The check uses `any(part in TEACHING_DIRS for part in root.parts)`
    # rather than `root.name in TEACHING_DIRS` so that a scan rooted at
    # `.../examples/good/` correctly identifies itself as a teaching-rooted
    # scan (since 'examples' is in the path parts).
    skip_teaching = not any(part in TEACHING_DIRS for part in root.parts)
    for p in root.rglob("*"):
        # rglob yields directories too — filter to regular files first
        # because `Path.suffix` on a directory is `''` and we want
        # directories to fall through naturally to the next check.
        if not p.is_file():
            continue
        # SKIP_DIRS check is BEFORE the teaching check so a directory
        # called `node_modules` inside `examples/` is still skipped
        # (we never want to descend into vendored code, full stop).
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        # Teaching-dir check: only active when the root is outside the
        # teaching dirs. This is what lets the test suite point measure()
        # directly at examples/ and still get the full file list back.
        if skip_teaching and any(part in TEACHING_DIRS for part in p.parts):
            continue
        # The final suffix check is the actual "is this a source file?"
        # gate. Only files with one of the audited extensions are
        # counted toward coverage.
        if p.suffix in SOURCE_EXTS:
            yield p


def _has_purpose_header(path: Path) -> bool:
    """Heuristic: first 10 lines contain a 'Purpose:' marker.

    The 10-line window is the comment at the top of the file explains
    why — module docstrings vary in length but rarely push 'Purpose:'
    past line 10. A larger window (e.g. 30) would catch files that put
    the marker below a long import block, but it would also raise
    false positives where 'Purpose:' appears inside a docstring or
    comment about another file.
    """
    try:
        # `errors="ignore"` lets us read files with mixed encodings
        # (e.g. Latin-1 sources in a UTF-8 repo) without crashing the
        # whole scan. The risk of miscounting is low because the
        # "Purpose:" check is a substring match on a single marker.
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            # Hard cap at 10 lines so a malicious 10GB file cannot
            # make us read the whole thing. EOF (`if not line`) ends
            # the loop early on short files.
            for _ in range(10):
                line = f.readline()
                if not line:
                    break
                # Substring match (not regex) is intentionally simple —
                # the marker is "Purpose:" with no variations, and a
                # regex would only add maintenance burden here.
                if "Purpose:" in line:
                    return True
    except OSError:
        # Permission errors, vanished files, etc. should fail open
        # to False rather than blowing up the whole scan. The metric
        # is a trend signal, not a security boundary.
        return False
    return False


def _measure_python(path: Path, report: CoverageReport) -> None:
    """AST-accurate metrics for Python: docstring coverage + LOC + comments.

    The AST path is preferred over the generic line-counter for Python
    because it gives us docstring presence without false positives from
    triple-quoted strings in regular code.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        # `ast.parse` is faster than `compile` for inspection because
        # it skips bytecode generation. We never execute the code.
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        # Unparseable Python (e.g. a 2/3 hybrid, an unfinished file
        # in a feature branch) — fall back to generic counters so the
        # rest of the scan still produces a number, even if a rougher one.
        _measure_generic(path, report)
        return

    # Total LOC and comment LOC: counted from the source text (string
    # split), not from the AST. The AST does not preserve all original
    # whitespace (it normalizes indentation in some nodes), so a
    # string-based count is more faithful to the "lines a human sees".
    lines = source.splitlines()
    report.total_loc += len(lines)
    # `lstrip().startswith("#")` catches indented comments too. A
    # naive `line.startswith("#")` would miss comments inside a
    # function body.
    report.comment_loc += sum(1 for ln in lines if ln.lstrip().startswith("#"))

    # Walk the whole AST looking for top-level + nested function
    # definitions. `ast.walk` is depth-first; we don't need order,
    # so a flat walk is fine.
    for node in ast.walk(tree):
        # Skip anything that isn't a function/method definition. This
        # includes classes (we don't score class docstrings here) and
        # lambdas (they can't carry docstrings anyway).
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # `_`-prefixed names are private by Python convention. The
        # underscore rule matches the test suite's expectation: only
        # "public" surface should be held to the docstring bar.
        if node.name.startswith("_"):
            continue
        report.public_funcs += 1
        # `ast.get_docstring` returns the first statement's string
        # value if it's an `Expr(Constant(str))`, else None. This
        # matches what Python's `help()` and IDE tooltips display.
        if ast.get_docstring(node):
            report.public_funcs_with_doc += 1


def _measure_generic(path: Path, report: CoverageReport) -> None:
    """Generic file metrics: total LOC + comment LOC for non-Python sources.

    Used for TypeScript, Go, Rust, Ruby, etc., and as a fallback when
    Python source is unparseable. We do NOT do AST walks here because
    the cost of bundling per-language parsers isn't worth the marginal
    accuracy gain over a line-based count.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        # Same fail-open as in _has_purpose_header — a missing file
        # should not abort the whole scan.
        return
    report.total_loc += len(lines)
    # The comment markers below are deliberately a tuple of prefixes,
    # not a regex. The set covers:
    #   //   — JS, TS, Go, Rust, Java, Kotlin, Swift single-line
    #   /*   — block comment opener (counted as a comment line even
    #          when it's actually `*/`; the few false positives are
    #          not worth a regex)
    #   *    — the body of a `/* ... */` block (each ` * foo` line)
    if path.suffix in {".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt"}:
        report.comment_loc += sum(
            1 for ln in lines if ln.lstrip().startswith(("//", "/*", "*"))
        )
    elif path.suffix == ".rb":
        # Ruby uses `#` like Python. Reusing the same prefix keeps
        # the metric logic simple even though the two languages have
        # different heredoc / multi-line semantics.
        report.comment_loc += sum(1 for ln in lines if ln.lstrip().startswith("#"))


# ── CLI ────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse args, run `measure`, print report, return gate rc.

    Args:
        argv: Argument vector. Defaults to `sys.argv[1:]` when None.

    Returns:
        0 if `overall_pct >= --min` (default 70), else 1.
    """
    parser = argparse.ArgumentParser(description="CoDocs coverage metrics")
    parser.add_argument("--path", required=True, help="repo path to scan")
    # --json is checked first by the caller (scripts/coverage.sh) so
    # that downstream parsers can rely on the schema even if human
    # output formatting changes in future versions.
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--min", type=int, default=DEFAULT_MIN_PERCENT,
                        help="minimum overall percent (gate)")
    args = parser.parse_args(argv)

    report = measure(args.path)
    if args.json:
        # The `asdict(report) | {...}` merge pattern (PEP 584 dict
        # union) keeps the dataclass fields in their declared order
        # and appends the computed percentages at the end. This is
        # the schema the bundle's `sin codocs check` JSON consumer
        # depends on — do not reorder the keys.
        out = asdict(report) | {
            "doc_md_pct": round(report.doc_md_pct, 1),
            "header_pct": round(report.header_pct, 1),
            "docstring_pct": round(report.docstring_pct, 1),
            "comment_density_pct": round(report.comment_density_pct, 1),
            "overall_pct": round(report.overall_pct, 1),
        }
        json.dump(out, sys.stdout, indent=2)
        # Trailing newline is required for many POSIX text tools that
        # refuse to process a file ending without one (wc -l, diff, etc).
        print()
    else:
        _print_human(report)

    # Gate decision: a single boolean on overall_pct. Individual axis
    # failures are visible in the human report but don't fail the CLI
    # — that keeps the metric useful for "trend over time" runs where
    # you only care about the overall number.
    return 0 if report.overall_pct >= args.min else 1


def _print_human(r: CoverageReport) -> None:
    """Render the coverage report as a column-aligned text table.

    The two-space gap between the label and the value is intentional —
    it makes the columns line up under any reasonable terminal width
    (80+ cols) without a fixed-width formatter dependency.
    """
    print(f"\nCoDocs coverage for: {r.path}")
    # File-level counts come first because they're the coarsest
    # signal — if these are wrong, the function-level numbers below
    # are meaningless.
    print(f"  Source files:         {r.source_files}")
    print(f"  With .doc.md:         {r.with_doc_md}  ({r.doc_md_pct:.1f}%)")
    print(f"  With Purpose header:  {r.with_purpose_header}  ({r.header_pct:.1f}%)")
    # Function-level metrics only apply to Python — for other languages
    # `public_funcs` is always 0 and the line below shows 0/0 (0.0%).
    print(f"  Public funcs:         {r.public_funcs}")
    print(f"  With docstring:       {r.public_funcs_with_doc}  ({r.docstring_pct:.1f}%)")
    print(f"  Total LOC:            {r.total_loc}")
    print(f"  Comment LOC:          {r.comment_loc}  ({r.comment_density_pct:.1f}%)")
    # The horizontal rule visually separates the inputs from the
    # overall score, which is the only number a CI gate typically acts on.
    print(f"  ────────────────────────────────")
    print(f"  Overall:              {r.overall_pct:.1f}%")


if __name__ == "__main__":
    sys.exit(main())
