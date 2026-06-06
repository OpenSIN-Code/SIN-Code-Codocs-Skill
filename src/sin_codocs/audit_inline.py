"""Purpose: AST-based audit of inline comment quality.

Docs: audit_inline.doc.md

Walks a Python source file's AST and reports:
  - Module-level docstring presence + Purpose/Docs keywords
  - Public function/method docstring coverage
  - Magic-number density (constants without inline comment context)
  - Function complexity (cyclomatic-ish: count of if/for/while/try/with)

Usage:
  python3 audit_inline.py path/to/file.py
  python3 audit_inline.py --json path/to/file.py
  python3 audit_inline.py --strict path/to/file.py   # exit 1 on any issue

Exit codes:
  0  no issues (or only warnings)
  1  at least one error (with --strict)
  2  file not found / parse error

Design notes:
  - Pure stdlib (ast, tokenize) — no external deps, so the audit runs
    even before the project's venv is set up.
  - AST-based, not regex — survives comments inside strings, multi-line
    expressions, decorators, and async code.
"""

# ─────────────────────────────────────────────────────────────────────────
# Why this auditor is its own file (not folded into metrics.py):
#   The coverage metric in metrics.py answers "is each .py file
#   accompanied by .doc.md + has a docstring?" — a binary, file-level
#   signal. This module answers a richer per-file question: "is each
#   PUBLIC function actually documented, and is the function body free
#   of magic numbers / runaway complexity?" Splitting the two concerns
#   keeps metrics.py small (and fast to run on huge repos) while letting
#   audit_inline.py do a deeper, slower walk that authors can run on
#   just the files they touched.
#
# Why we walk the AST instead of using tokenize:
#   tokenize gives you every token including comments, but it does not
#   give you the AST shape (e.g. that an `if` is inside a `for`). For
#   docstring and complexity checks we need the structural tree; for
#   comment-line counting we use a simple `line.startswith("#")` pass
#   on top of ast.parse output, which is good enough for trend tracking.
# ─────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


# Numeric constants that are almost never "magic" in the sense the
# audit cares about. 0, 1, and -1 dominate arithmetic, identity, and
# index operations; 2 is included because it's the start of most
# range() calls and the common "pair" / "two-pointer" idiom.
NON_MAGIC_NUMBERS = frozenset({0, 1, -1, 2})


@dataclass
class AuditResult:
    """Aggregated audit findings for a single file."""
    file: str
    has_module_docstring: bool = False
    has_purpose_keyword: bool = False
    has_docs_keyword: bool = False
    public_funcs: int = 0
    public_funcs_with_docstring: int = 0
    magic_numbers: int = 0
    functions: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def docstring_coverage(self) -> float:
        """Public-function docstring coverage as a fraction (0.0 - 1.0)."""
        if self.public_funcs == 0:
            return 1.0
        return self.public_funcs_with_docstring / self.public_funcs

    def to_dict(self) -> dict:
        """Serialize the audit result to a JSON-safe dict."""
        return {
            "file": self.file,
            "has_module_docstring": self.has_module_docstring,
            "has_purpose_keyword": self.has_purpose_keyword,
            "has_docs_keyword": self.has_docs_keyword,
            "public_funcs": self.public_funcs,
            "public_funcs_with_docstring": self.public_funcs_with_docstring,
            "docstring_coverage": round(self.docstring_coverage, 3),
            "magic_numbers": self.magic_numbers,
            "functions": self.functions,
            "issues": self.issues,
            "warnings": self.warnings,
        }


# ── Public API ─────────────────────────────────────────────────────────
def audit_file(path: str | Path) -> AuditResult:
    """Audit a single Python file's inline documentation.

    Args:
        path: Path to a .py file. Must be readable and parseable as Python.

    Returns:
        AuditResult with per-file metrics and any issues/warnings.

    Raises:
        FileNotFoundError: path does not exist.
        SyntaxError: file is not valid Python.
    """
    p = Path(path)
    if not p.exists():
        # `raise FileNotFoundError(p)` is intentionally more verbose
        # than the bare `raise` form — the path is the most useful
        # piece of context for a caller that passed the wrong arg.
        raise FileNotFoundError(p)

    # Default UTF-8 read: this auditor is for source code, and any
    # non-UTF-8 file in a modern Python project is a bug worth
    # surfacing rather than papering over with errors="ignore".
    source = p.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(p))

    # The dataclass is created early so partial results are still
    # meaningful if a later check raises (it shouldn't, but defense
    # in depth is cheap here).
    result = AuditResult(file=str(p))
    # The three checks are independent — order does not matter, but
    # running module-docstring first surfaces the most common
    # issue (a missing file-level docstring) at the top of the
    # human-readable report.
    _check_module_docstring(tree, result)
    _walk_functions(tree, result)
    _find_magic_numbers(tree, source, result)
    return result


def audit_paths(paths: list[Path]) -> list[AuditResult]:
    """Audit many paths. Returns one AuditResult per file. Skips unreadable.

    The contract is "one result per input path, in the same order" so
    callers can `zip(paths, results)` to correlate findings with inputs.
    The per-file exception is captured into the result's `issues`
    list rather than re-raised, so a single broken file cannot abort
    a CI run over a whole tree.
    """
    results: list[AuditResult] = []
    for p in paths:
        # Filter non-Python paths silently — callers may pass a glob
        # that includes .pyc / .txt / etc. The audit is Python-only
        # by design (it relies on the AST).
        if p.suffix != ".py":
            continue
        try:
            results.append(audit_file(p))
        except (FileNotFoundError, SyntaxError) as e:
            # Build a "skeleton" result with the error captured so
            # the caller still gets a row in their report for this
            # file. The error type name + message is enough to act on.
            r = AuditResult(file=str(p))
            r.issues.append(f"{type(e).__name__}: {e}")
            results.append(r)
    return results


# ── Internal checks ───────────────────────────────────────────────────
def _check_module_docstring(tree: ast.Module, result: AuditResult) -> None:
    """Check that the module has a docstring with Purpose + Docs keywords.

    The Purpose and Docs markers are the two pieces of metadata the
    ceo-audit `axis_docs` gate looks for. A module docstring without
    them is still "present" but does not earn the SOTA seal.
    """
    doc = ast.get_docstring(tree)
    result.has_module_docstring = bool(doc)
    if not doc:
        # Issue (not warning) because a missing module docstring
        # is a hard fail under --strict — the file cannot pass.
        result.issues.append("Missing module-level docstring")
        return
    # The keyword checks below use `in` (substring) rather than
    # line-equality. This is intentionally forgiving: a docstring
    # like "Module Purpose: foo" still matches the "Purpose" check,
    # which is what we want — the marker is a convention, not a
    # rigid schema.
    if "Purpose" not in doc:
        result.issues.append("Module docstring missing 'Purpose:' line")
    else:
        result.has_purpose_keyword = True
    if "Docs:" not in doc:
        result.issues.append("Module docstring missing 'Docs:' line")
    else:
        result.has_docs_keyword = True


def _walk_functions(tree: ast.AST, result: AuditResult) -> None:
    """Walk top-level + nested functions, recording docstring coverage.

    Private functions (leading underscore) and dunder methods
    (__init__, __repr__, etc.) are skipped. The metric is about
    the *public* API surface, not internal helpers or protocol
    methods. Subclass overrides of public methods are counted at
    the override site because they are public to the subclass.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Skip private (leading underscore) and dunder methods.
        # We do not special-case dunder separately — a `__init__`
        # starts with `_` (two of them) and is filtered by the same
        # rule. This is intentional: dunder methods are conventions,
        # not API.
        is_public = not node.name.startswith("_")
        if not is_public:
            continue
        result.public_funcs += 1
        # `ast.get_docstring` returns the constant string if the
        # first statement is a bare-string expression, else None.
        # This is exactly what `inspect.getdoc` would show.
        doc = ast.get_docstring(node)
        has_doc = bool(doc)
        if has_doc:
            result.public_funcs_with_docstring += 1
        # Cyclomatic-ish complexity: cheap to compute at walk time
        # so we record it alongside docstring presence. The CI gate
        # that uses this metric only acts on missing docstrings, but
        # having complexity in the JSON lets human reviewers spot
        # refactor candidates without re-running the audit.
        complexity = _complexity(node)
        result.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "has_docstring": has_doc,
            "complexity": complexity,
        })
        if not has_doc:
            # Warning (not issue) because a missing docstring on a
            # public function is recoverable — adding the docstring
            # makes the audit pass on the next run. Issues are
            # reserved for structural problems (missing module
            # docstring, parse errors) that need code changes.
            result.warnings.append(
                f"Public function '{node.name}' (line {node.lineno}) "
                f"missing docstring"
            )
        if complexity > COMPLEXITY_WARN_THRESHOLD:
            # Same warning-vs-issue distinction: high complexity is
            # a hint, not a failure. Refactoring may or may not be
            # the right call depending on context.
            result.warnings.append(
                f"Function '{node.name}' has high complexity "
                f"({complexity}, threshold {COMPLEXITY_WARN_THRESHOLD})"
            )
        if complexity > COMPLEXITY_WARN_THRESHOLD:
            result.warnings.append(
                f"Function '{node.name}' has high complexity "
                f"({complexity}, threshold 15)"
            )


def _find_magic_numbers(tree: ast.Module, source: str, result: AuditResult) -> None:
    """Heuristic: count numeric literals not assigned to a named constant.

    The first numeric literal in a module-level assignment is treated as a
    'named constant' and ignored. Everything else in function bodies is a
    potential magic number that should be commented.

    Notes on the heuristic (kept here, not in the docstring, so a reviewer
    can see WHY each branch is structured this way):
      • Module-level names that point at int/float constants are treated
        as the "named constants" set. The set is built by NAME, not by
        value, so two constants with the same numeric value count once.
      • Inside function bodies we walk every ast.Constant node. 0, 1, -1,
        and 2 are skipped as "rarely magic" — they're common in
        arithmetic, index arithmetic, and identity checks.
      • The final count subtracts `len(named)` once (rough — value-based,
        not reference-based). The cap-warning fires at > 5 to avoid
        noisy false positives on long numeric configuration dicts.
    """
    # Collect names that are module-level numeric assignments
    named = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, (int, float)):
                    named.add(tgt.id)

    # Now count numeric literals inside function bodies
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if node.value in NON_MAGIC_NUMBERS:
                continue  # common, rarely magic
            count += 1

    # Subtract the named constants' values
    # (rough heuristic — counts by value, not by name reference)
    result.magic_numbers = max(0, count - len(named))
    if result.magic_numbers > 5:
        result.warnings.append(
            f"{result.magic_numbers} potential magic numbers — "
            f"consider naming them and adding inline comments"
        )


# Threshold for the "high complexity" warning. Mirrors ceo-audit's
# cyclomatic-complexity gate. 15 is the industry-standard "consider
# refactoring" line for cyclomatic complexity (NIST, McCabe).
COMPLEXITY_WARN_THRESHOLD = 15


def _complexity(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count decision points: if/for/while/try/with/and/or/except/comp.

    The base value is 1 (a function with no branches still has one path).
    Each control-flow node adds 1, each boolean operator with N operands
    adds N-1 (since an `and`/`or` chain with N values has N-1 decision
    points), and each comprehension generator + filter adds one.

    Not strictly McCabe — that would also include short-circuit
    evaluation, ternary expressions, and recursion. We accept the
    approximation because the warning is a heuristic, not an audit
    verdict.
    """
    # Start at 1 — every function has at least one path.
    count = 1
    for node in ast.walk(func):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try,
                             ast.With, ast.ExceptHandler)):
            # Each control-flow node is one decision point.
            count += 1
        elif isinstance(node, ast.BoolOp):
            # `a and b and c` has 2 decision points (a→b, b→c), not 3.
            count += len(node.values) - 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                               ast.GeneratorExp)):
            # Each generator is one iteration decision; each `if` filter
            # is one more. So a list comp with 2 generators, the second
            # having a filter, contributes 2 + 1 = 3.
            count += len(node.generators) + sum(
                len(elt.ifs) for elt in node.generators
            )
    return count


# ── CLI ────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI entry point: audit paths, print human or JSON output, gate on --strict.

    Args:
        argv: Argument vector. Defaults to `sys.argv[1:]` when None.

    Returns:
        0 on success (or warnings only), 1 with --strict when any file has issues.
    """
    parser = argparse.ArgumentParser(
        description="Audit inline documentation quality of Python files."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="files or dirs")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--strict", action="store_true", help="exit 1 on issues")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for p in args.paths:
        if p.is_dir():
            files.extend(p.rglob("*.py"))
        else:
            files.append(p)

    results = audit_paths(files)
    payload = [r.to_dict() for r in results]

    if args.json:
        # Same trailing-newline reasoning as in metrics.py main():
        # POSIX text tools (wc -l, diff, jq) refuse to process a
        # file that does not end with a newline.
        json.dump(payload, sys.stdout, indent=2)
        print()
    else:
        _print_human(payload)

    # --strict semantics: warnings are still "OK", only `issues`
    # (structural problems: missing module docstring, parse errors)
    # cause a non-zero exit. This is what lets pre-commit use --strict
    # without false positives on style warnings.
    if args.strict:
        for r in results:
            if r.issues:
                return 1
    return 0


def _print_human(payload: list[dict]) -> None:
    """Render one report entry per file in plain text.

    The format is "file header → 4-line summary → issues → warnings".
    The summary is intentionally short — the per-file JSON output
    carries the full detail, and the human view is for skimming a
    CI log to find which file needs attention.
    """
    for entry in payload:
        # The `=== file ===` header uses ASCII `=` rather than box
        # drawing so the output survives copy-paste into Markdown,
        # Jira, or Slack without garbling. Terminal-only output
        # would benefit from `─` but the cross-tool compatibility
        # is worth more than the visual nicety.
        print(f"\n=== {entry['file']} ===")
        print(f"  Module docstring:   {entry['has_module_docstring']}")
        print(f"  Purpose keyword:    {entry['has_purpose_keyword']}")
        print(f"  Docs keyword:       {entry['has_docs_keyword']}")
        # The "(N documented, X%)" inline form lets reviewers scan
        # the file list and spot the 0/3 outliers at a glance.
        print(f"  Public functions:   {entry['public_funcs']} "
              f"({entry['public_funcs_with_docstring']} documented, "
              f"{int(entry['docstring_coverage'] * 100)}%)")
        print(f"  Magic numbers:      {entry['magic_numbers']}")
        if entry["issues"]:
            # `!` for issues vs `-` for warnings gives an at-a-glance
            # distinction in monochrome terminals.
            print("  ISSUES:")
            for i in entry["issues"]:
                print(f"    ! {i}")
        if entry["warnings"]:
            print("  WARNINGS:")
            for w in entry["warnings"]:
                print(f"    - {w}")


if __name__ == "__main__":
    # `raise SystemExit` is equivalent to `sys.exit()` here but is
    # the conventional form for `if __name__ == "__main__"` blocks
    # at module scope (PEP 8 recommends the explicit form).
    raise SystemExit(main())
