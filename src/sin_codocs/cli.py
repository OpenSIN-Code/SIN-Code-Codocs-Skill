# Purpose: Unified CLI for sin-codocs — exposes validator and sprint subcommands
# Docs: cli.doc.md
"""SIN CoDocs CLI — unified entry point for validator + sprint operations.

Subcommands are split into two groups:

  - **Read-only (validator):** check, check-inline, list, coverage
  - **Read-write (executor):** new-doc-md, new-module, init, sprint,
    scan, generate, diff, status, install-skill

Usage:
    sin-codocs check <path> [--json]
    sin-codocs check-inline <path> [--json]
    sin-codocs list <path>
    sin-codocs coverage <path> [--min N]
    sin-codocs new-doc-md <file>
    sin-codocs new-module <file>
    sin-codocs init <repo-path>
    sin-codocs sprint <repo-path> [--auto] [--commit] [--dry-run]
    sin-codocs scan <repo-path> [--json]
    sin-codocs generate <file> [--stdout] [--force]
    sin-codocs diff <repo-path>
    sin-codocs status <repo-path> [--min N]
    sin-codocs install-skill
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def _delegate_to_script(script_name: str, argv: list[str]) -> int:
    """Run a shell script from the scripts/ directory.

    Sprint/validator scripts stay as shell so they can be invoked
    from CI without installing the Python package.
    """
    script_dir = Path(__file__).parent.parent.parent / "scripts"
    script = script_dir / script_name
    if not script.is_file():
        print(f"Script not found: {script}", file=sys.stderr)
        return 1
    return subprocess.call(["bash", str(script)] + argv)


def cmd_check(args: argparse.Namespace) -> int:
    """Run validator check (delegates to scripts/check.sh)."""
    argv = []
    if args.path:
        argv.append(args.path)
    if args.json:
        argv.append("--json")
    return _delegate_to_script("check.sh", argv)


def cmd_check_inline(args: argparse.Namespace) -> int:
    """Run inline-doc check (delegates to audit_inline.py directly)."""
    from .audit_inline import audit_inline
    from .metrics import DEFAULT_EXCLUDE
    path = args.path or "."
    issues = audit_inline(path, exclude=DEFAULT_EXCLUDE)
    if args.json:
        print(json.dumps([i.to_dict() for i in issues], indent=2))
    else:
        for issue in issues:
            print(f"{issue.path}:{issue.line}  [{issue.kind}] {issue.detail}")
    return 0 if not issues else 1


def cmd_list(args: argparse.Namespace) -> int:
    """List all CoDocs references in a directory."""
    return _delegate_to_script("check.sh", [args.path or "."])


def cmd_coverage(args: argparse.Namespace) -> int:
    """Print coverage report (delegates to scripts/coverage.sh)."""
    argv = []
    if args.path:
        argv.append(args.path)
    if args.min is not None:
        argv.extend(["--min", str(args.min)])
    return _delegate_to_script("coverage.sh", argv)


def cmd_new_doc_md(args: argparse.Namespace) -> int:
    """Create a new .doc.md companion for a source file."""
    return _delegate_to_script("new-doc-md.sh", [args.file])


def cmd_new_module(args: argparse.Namespace) -> int:
    """Scaffold a new module with CoDocs (delegates to scripts/new-module.sh)."""
    return _delegate_to_script("new-module.sh", [args.file])


def cmd_init(args: argparse.Namespace) -> int:
    """Bootstrap a repo with CoDocs (delegates to scripts/init.sh)."""
    return _delegate_to_script("init.sh", [args.path])


def cmd_sprint(args: argparse.Namespace) -> int:
    """Run a CoDocs coverage sprint (delegates to scripts/sprint.sh)."""
    argv = [args.path or "."]
    if args.auto:
        argv.append("--auto")
    if args.commit:
        argv.append("--commit")
    if args.dry_run:
        argv.append("--dry-run")
    if args.min is not None:
        argv.extend(["--min", str(args.min)])
    return _delegate_to_script("sprint.sh", argv)


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan for CoDocs gaps (delegates to scripts/scan.sh)."""
    argv = [args.path or "."]
    if args.json:
        argv.append("--json")
    return _delegate_to_script("scan.sh", argv)


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate a draft .doc.md (delegates to scripts/generate.sh)."""
    argv = [args.file]
    if args.stdout:
        argv.append("--stdout")
    if args.force:
        argv.append("--force")
    return _delegate_to_script("generate.sh", argv)


def cmd_diff(args: argparse.Namespace) -> int:
    """Preview a sprint (delegates to scripts/diff.sh)."""
    argv = [args.path or "."]
    if args.json:
        argv.append("--json")
    return _delegate_to_script("diff.sh", argv)


def cmd_status(args: argparse.Namespace) -> int:
    """One-screen coverage status (delegates to scripts/status.sh)."""
    argv = [args.path or "."]
    if args.min is not None:
        argv.extend(["--min", str(args.min)])
    return _delegate_to_script("status.sh", argv)


def cmd_install_skill(args: argparse.Namespace) -> int:
    """Install the skill locally (delegates to scripts/install-skill.sh)."""
    return _delegate_to_script("install-skill.sh", [])


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="sin-codocs",
        description="SIN CoDocs — Co-located docs standard + sprint executor",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # Read-only (validator)
    p = sub.add_parser("check", help="Verify all Docs: references resolve")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("check-inline", help="Check inline doc headers + docstrings")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check_inline)

    p = sub.add_parser("list", help="List all CoDocs references")
    p.add_argument("path", nargs="?", default=".")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("coverage", help="Print coverage report")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--min", type=int, default=None)
    p.set_defaults(func=cmd_coverage)

    # Read-write (executor)
    p = sub.add_parser("new-doc-md", help="Create one .doc.md companion")
    p.add_argument("file")
    p.set_defaults(func=cmd_new_doc_md)

    p = sub.add_parser("new-module", help="Scaffold a new module with CoDocs")
    p.add_argument("file")
    p.set_defaults(func=cmd_new_module)

    p = sub.add_parser("init", help="Bootstrap a repo with CoDocs")
    p.add_argument("path")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("sprint", help="Run a CoDocs coverage sprint")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--auto", action="store_true")
    p.add_argument("--commit", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--min", type=int, default=None)
    p.set_defaults(func=cmd_sprint)

    p = sub.add_parser("scan", help="Scan for CoDocs gaps")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("generate", help="Generate a draft .doc.md")
    p.add_argument("file")
    p.add_argument("--stdout", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("diff", help="Preview a sprint (no changes)")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("status", help="One-screen coverage status")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--min", type=int, default=None)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("install-skill", help="Install the skill locally")
    p.set_defaults(func=cmd_install_skill)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
