# Purpose: sin-codocs package — CoDocs Standard + Sprint Executor
# Docs: __init__.doc.md
"""SIN CoDocs — Standard + Sprint Executor (merged package).

Two-layer CoDocs tool. Public API:

  Validator layer (read-only):
    - audit_inline.audit_file / audit_paths / AuditResult
    - metrics.measure / CoverageReport

  Executor layer (sprint):
    - scanner.scan_repo / ScanResult / Gap
    - generator.generate_draft / write_draft / extract_facts / SourceFacts
    - reporter.format_gap_table / format_gap_listing / format_sprint_summary / format_diff
    - sprint_metrics.run_sprint_metrics / SprintReport

  Template helpers:
    - template.load_config / retry_with_backoff

The ``sin_codocs`` namespace is the single entry point — subcommands
live in ``sin_codocs.cli``.
"""

from .template import load_config, retry_with_backoff
from .audit_inline import audit_file, audit_paths, AuditResult
from .metrics import measure, CoverageReport

__version__ = "1.0.0"
__all__ = [
    # Validator
    "audit_file",
    "audit_paths",
    "AuditResult",
    "measure",
    "CoverageReport",
    # Template helpers
    "load_config",
    "retry_with_backoff",
]
