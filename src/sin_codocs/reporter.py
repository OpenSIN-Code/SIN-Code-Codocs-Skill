"""Purpose: Format scanner output as a human-readable report.

Docs: reporter.doc.md

Takes a `ScanResult` (from `lib/scanner.py`) or a `SprintReport`
(from `lib/metrics.py`) and renders it for humans or machines.

Three output modes:

  - `format_gap_table(result)`     — table of gap counts by kind
  - `format_gap_listing(result)`   — full per-file list
  - `format_sprint_summary(sprint)` — overall coverage + sprint gaps
  - `format_diff(before, after)`   — before/after delta for sprint.sh

Pure formatting: no I/O, no subprocess, no mutation. Caller decides
where the output goes (stdout, file, log, …).

Usage:
  from reporter import format_gap_table, format_sprint_summary
  print(format_gap_table(scan_result))
  print(format_sprint_summary(sprint_report))
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scanner import ScanResult
    from .metrics import SprintReport


# ── Public API ─────────────────────────────────────────────────────────
def format_gap_table(result: "ScanResult") -> str:
    """One-line-per-kind summary, suitable for the bottom of scan output."""
    if result.error:
        return f"ERROR: {result.error}"
    lines = [
        f"Source files scanned: {result.scanned_count}",
        f"Gaps by kind:",
    ]
    for kind in ("MISSING_COMPANION", "MISSING_HEADER", "MISSING_DOCSTRING"):
        n = result.by_kind.get(kind, 0)
        marker = "→" if n > 0 else " "
        lines.append(f"  {marker} {kind:20s} {n}")
    total = sum(result.by_kind.values())
    lines.append(f"  ────────────────────────────────")
    lines.append(f"    {'TOTAL':20s} {total}")
    return "\n".join(lines)


def format_gap_listing(result: "ScanResult", *, max_lines: int = 200) -> str:
    """Per-file listing of every gap. Capped to max_lines."""
    if result.error:
        return f"ERROR: {result.error}"
    lines: list[str] = []
    by_kind: dict[str, list] = {"MISSING_COMPANION": [],
                                "MISSING_HEADER": [],
                                "MISSING_DOCSTRING": []}
    for g in result.gaps:
        by_kind.setdefault(g.kind, []).append(g)

    for kind in ("MISSING_COMPANION", "MISSING_HEADER", "MISSING_DOCSTRING"):
        items = by_kind.get(kind, [])
        if not items:
            continue
        lines.append(f"\n## {kind}  ({len(items)} file"
                     f"{'s' if len(items) != 1 else ''})")
        for g in items[:max_lines]:
            detail = f" — {g.detail}" if g.detail else ""
            lines.append(f"  - {g.rel_path}{detail}")
        if len(items) > max_lines:
            lines.append(f"  - … and {len(items) - max_lines} more (truncated)")

    if not any(by_kind.values()):
        lines.append("\n✓ No CoDocs gaps found — 100% covered.")
    return "\n".join(lines)


def format_sprint_summary(sprint) -> str:
    """One-shot summary combining coverage % + sprint gap counts.

    `sprint` is a `SprintReport` (lib/metrics.py).
    """
    if sprint.sprint_error:
        return f"ERROR: {sprint.sprint_error}"
    lines = [
        f"Sprint status for: {sprint.sprint_repo_path}",
        f"  Overall coverage:       {sprint.overall_pct:.1f}%",
        f"  .doc.md coverage:       {sprint.doc_md_pct:.1f}%   ({sprint.with_doc_md}/{sprint.source_files})",
        f"  Purpose/Docs coverage:  {sprint.header_pct:.1f}%   ({sprint.with_purpose_header}/{sprint.source_files})",
        f"  Docstring coverage:     {sprint.docstring_pct:.1f}%   ({sprint.public_funcs_with_doc}/{sprint.public_funcs})",
        f"  Comment density:        {sprint.comment_density_pct:.1f}%",
        f"  ────────────────────────────────",
        f"  Files needing .doc.md:  {sprint.sprint_files_remaining}",
        f"  Files needing header:   {sprint.sprint_header_remaining}",
        f"  Last scan:              {sprint.sprint_runtime_seconds:.2f}s",
    ]
    return "\n".join(lines)


def format_diff(before, after) -> str:
    """Render a before/after delta table for `sprint.sh --commit`.

    `before` and `after` are `SprintReport` instances.
    """
    def delta(field: str, before_val, after_val, fmt: str = "{}") -> str:
        """Render one row of the before/after delta table.

        Args:
            field: Human label for the metric.
            before_val: Value before the sprint.
            after_val: Value after the sprint.
            fmt: Format spec for both values (default `'{}'`).

        Returns:
            One row of the delta table, with a `+` or `-` sign
            for non-zero changes.
        """
        try:
            d = (after_val or 0) - (before_val or 0)
        except TypeError:
            return f"  {field:24s}  ?"
        sign = "+" if d > 0 else ("-" if d < 0 else " ")
        return f"  {field:24s}  {fmt.format(before_val):>8}  →  {fmt.format(after_val):<8}  ({sign}{abs(d)})"

    lines = [
        f"Coverage delta: {before.sprint_repo_path}",
        f"  {'':24s}  {'BEFORE':>8}       {'AFTER':<8}",
        delta("Overall %",       before.overall_pct,  after.overall_pct,  "{:.1f}"),
        delta(".doc.md %",        before.doc_md_pct,   after.doc_md_pct,   "{:.1f}"),
        delta("Purpose/Docs %",   before.header_pct,   after.header_pct,   "{:.1f}"),
        delta("Docstring %",      before.docstring_pct, after.docstring_pct, "{:.1f}"),
        delta("Files w/ doc.md",  before.with_doc_md,  after.with_doc_md),
        delta("Files needing",    before.sprint_files_remaining, after.sprint_files_remaining),
    ]
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the reporter.

    Reconstructs a ScanResult or SprintReport from a JSON file
    and prints it via the matching format_* helper. The reporter
    can also render a before/after diff when both --before and
    --after point to saved JSON. Returns 0 on success, 2 on
    missing args.
    """
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Format scanner / metrics output for humans."
    )
    parser.add_argument("--scanner-json", help="path to scanner JSON output")
    parser.add_argument("--metrics-json", help="path to metrics JSON output")
    parser.add_argument("--before", help="path to before-metrics JSON")
    parser.add_argument("--after", help="path to after-metrics JSON")
    parser.add_argument("--mode", default="table",
                        choices=("table", "listing", "summary", "diff"),
                        help="output mode")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from scanner import ScanResult
    from metrics import SprintReport

    if args.scanner_json:
        raw = json.loads(Path(args.scanner_json).read_text())
        sr = ScanResult(repo_path=raw["repo_path"],
                        scanned_count=raw["scanned_count"],
                        by_kind=raw["by_kind"])
        sr.gaps = [type("G", (), g) for g in raw["gaps"]]
        if args.mode == "listing":
            print(format_gap_listing(sr))
        else:
            print(format_gap_table(sr))
        return 0

    if args.metrics_json:
        raw = json.loads(Path(args.metrics_json).read_text())
        sp = SprintReport(**{k: v for k, v in raw.items()
                             if k in SprintReport.__dataclass_fields__})
        print(format_sprint_summary(sp))
        return 0

    if args.before and args.after:
        b = json.loads(Path(args.before).read_text())
        a = json.loads(Path(args.after).read_text())
        before_sp = SprintReport(**{k: v for k, v in b.items()
                                    if k in SprintReport.__dataclass_fields__})
        after_sp = SprintReport(**{k: v for k, v in a.items()
                                   if k in SprintReport.__dataclass_fields__})
        print(format_diff(before_sp, after_sp))
        return 0

    print("ERROR: pass --scanner-json, --metrics-json, or --before/--after",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
