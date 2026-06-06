"""Purpose: Thin wrapper around sin-codocs metrics for sprint-specific reporting.

Docs: metrics.doc.md

This module does NOT reimplement the CoDocs coverage math. It
subprocesses the real sin-codocs `lib/metrics.py` and adds sprint-only
metadata:

  - `sprint_files_remaining` — count of source files lacking .doc.md
  - `sprint_header_remaining` — count lacking Purpose/Docs header
  - `sprint_runtime_seconds` — wall-clock time of the scan
  - `sprint_repo_path` — absolute path of the scanned repo

The single source of truth for "what is coverage" is the sin-codocs
skill's `lib/metrics.py`. If the upstream math ever changes, this
wrapper picks it up automatically.

Usage:
  from metrics import run_sprint_metrics
  report = run_sprint_metrics("/path/to/repo")
  print(report["overall_pct"], report["sprint_files_remaining"])
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


# ── Constants ──────────────────────────────────────────────────────────
# Path to the upstream sin-codocs metrics library. Single integration
# point — if the upstream path changes, change it here. Wrapping via
# subprocess (not import) gives us a clean process boundary, so the
# upstream skill can be updated without breaking the sprint tool.
# Default: ~/.config/opencode/skills/sin-codocs/src/sin_codocs/metrics.py
# (the post-merge location, where validator + executor live in one repo)
# Override via SINCODOCS_METRICS_PATH env var for non-standard installs.
SINCODOCS_METRICS = Path(
    os.environ.get(
        "SINCODOCS_METRICS_PATH",
        str(
            Path.home()
            / ".config/opencode/skills/sin-codocs/src/sin_codocs/metrics.py"
        ),
    )
)

# 5-minute timeout — long enough for a 50k-file monorepo, short enough
# to surface real failures fast. Larger repos should chunk by --path.
SUBPROCESS_TIMEOUT = 300

# Default coverage gate when --min is not specified. Matches the gate
# sin-codocs ships with; the sprint tool never silently lowers the bar.
DEFAULT_MIN = 70


# ── Public data types ─────────────────────────────────────────────────
@dataclass
class SprintReport:
    """Combined coverage + sprint-gap metrics for one repo path.

    Fields are split into two groups:
      - Upstream fields (source_files, with_doc_md, …) are copied
        verbatim from `sin-codocs/lib/metrics.py:CoverageReport`.
      - Sprint fields (sprint_files_remaining, sprint_runtime_seconds,
        …) are derived in `run_sprint_metrics`.
    """
    sprint_repo_path: str = ""
    source_files: int = 0
    with_doc_md: int = 0
    with_purpose_header: int = 0
    public_funcs: int = 0
    public_funcs_with_doc: int = 0
    overall_pct: float = 0.0
    doc_md_pct: float = 0.0
    header_pct: float = 0.0
    docstring_pct: float = 0.0
    comment_density_pct: float = 0.0
    sprint_files_remaining: int = 0  # = source_files - with_doc_md
    sprint_header_remaining: int = 0  # = source_files - with_purpose_header
    sprint_runtime_seconds: float = 0.0  # wall-clock of the upstream call
    sprint_error: str = ""  # non-empty iff the upstream failed


# ── Public API ─────────────────────────────────────────────────────────
def run_sprint_metrics(repo_path: str | Path) -> SprintReport:
    """Measure coverage + sprint gaps for a repo.

    Spawns the upstream sin-codocs metrics library as a subprocess so
    we never duplicate the math. Adds sprint-specific fields on top.

    Args:
        repo_path: Directory to scan.

    Returns:
        SprintReport with both the upstream coverage fields and the
        sprint gap counts. On upstream failure, `sprint_error` is set
        and other fields default to 0.
    """
    repo = Path(repo_path).resolve()
    report = SprintReport(sprint_repo_path=str(repo))
    if not SINCODOCS_METRICS.exists():
        # Fail closed — a missing upstream must be visible, not a 0% pass.
        report.sprint_error = f"upstream sin-codocs metrics not found: {SINCODOCS_METRICS}"
        return report

    t0 = time.monotonic()
    try:
        # Subprocess boundary: one place to change if upstream evolves.
        # 5-minute timeout is the constant SUBPROCESS_TIMEOUT above.
        proc = subprocess.run(
            [sys.executable, str(SINCODOCS_METRICS),
             "--path", str(repo), "--json"],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        report.sprint_error = f"upstream metrics timed out after {SUBPROCESS_TIMEOUT}s"
        return report
    except OSError as e:
        # File not found, permission denied, etc. — surface, don't guess.
        report.sprint_error = f"failed to spawn upstream: {e}"
        return report
    elapsed = time.monotonic() - t0
    report.sprint_runtime_seconds = round(elapsed, 3)

    # Exit 0/1 are normal (1 = below --min in upstream, not an error).
    # Anything else is a real failure we should surface.
    if proc.returncode not in (0, 1):
        # Exit 0/1 are normal (1 = below --min, not an error). Anything else is.
        report.sprint_error = f"upstream exited {proc.returncode}: {proc.stderr[:200]}"
        return report

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        report.sprint_error = f"upstream produced invalid JSON: {e}"
        return report

    # Copy upstream fields verbatim
    report.source_files = data.get("source_files", 0)
    report.with_doc_md = data.get("with_doc_md", 0)
    report.with_purpose_header = data.get("with_purpose_header", 0)
    report.public_funcs = data.get("public_funcs", 0)
    report.public_funcs_with_doc = data.get("public_funcs_with_doc", 0)
    report.overall_pct = float(data.get("overall_pct", 0.0))
    report.doc_md_pct = float(data.get("doc_md_pct", 0.0))
    report.header_pct = float(data.get("header_pct", 0.0))
    report.docstring_pct = float(data.get("docstring_pct", 0.0))
    report.comment_density_pct = float(data.get("comment_density_pct", 0.0))

    # Sprint-specific derived fields
    report.sprint_files_remaining = max(
        0, report.source_files - report.with_doc_md
    )
    report.sprint_header_remaining = max(
        0, report.source_files - report.with_purpose_header
    )
    return report


def to_dict(report: SprintReport) -> dict:
    """Render a SprintReport as a JSON-safe dict."""
    return asdict(report)


# ── CLI ────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the sprint metrics wrapper.

    Parses --path (required), --json, and --min (default 70),
    runs `run_sprint_metrics`, and prints either a JSON payload
    or a human sprint summary to stdout. Returns 0 on coverage
    above --min, 1 on coverage below --min, 2 on bad args or
    upstream error.
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="Sprint-specific CoDocs metrics (wraps sin-codocs)"
    )
    parser.add_argument("--path", required=True, help="repo path to scan")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--min", type=int, default=70,
                        help="minimum overall percent (gate, default 70)")
    args = parser.parse_args(argv)

    report = run_sprint_metrics(args.path)
    if args.json:
        json.dump(to_dict(report), sys.stdout, indent=2)
        print()
    else:
        if report.sprint_error:
            print(f"ERROR: {report.sprint_error}", file=sys.stderr)
            return 2
        _print_human(report)

    return 0 if report.overall_pct >= 70 else 1


def _print_human(r: SprintReport) -> None:
    print(f"\nSprint coverage for: {r.sprint_repo_path}")
    print(f"  Source files:           {r.source_files}")
    print(f"  With .doc.md:           {r.with_doc_md}  ({r.doc_md_pct:.1f}%)")
    print(f"  With Purpose header:    {r.with_purpose_header}  ({r.header_pct:.1f}%)")
    print(f"  Public funcs:           {r.public_funcs}")
    print(f"  With docstring:         {r.public_funcs_with_doc}  ({r.docstring_pct:.1f}%)")
    print(f"  Comment density:        {r.comment_density_pct:.1f}%")
    print(f"  ────────────────────────────────")
    print(f"  Overall coverage:       {r.overall_pct:.1f}%")
    print(f"  Sprint gap (no doc):    {r.sprint_files_remaining} files")
    print(f"  Sprint gap (no header): {r.sprint_header_remaining} files")
    print(f"  Scan time:              {r.sprint_runtime_seconds:.2f}s")


if __name__ == "__main__":
    sys.exit(main())
