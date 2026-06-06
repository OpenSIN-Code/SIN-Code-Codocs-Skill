"""Purpose: Unit tests for the reporter.

Docs: test_reporter.doc.md

Tests the pure formatting functions in `src/sin_codocs/reporter.py`. No I/O,
no subprocess — just `format_*` calls and string assertions.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / 'lib'
sys.path.insert(0, str(LIB_DIR))
from sin_codocs.reporter import format_gap_table, format_gap_listing, format_sprint_summary, format_diff
from sin_codocs.scanner import ScanResult, Gap
from sin_codocs.sprint_metrics import SprintReport

def _make_result() -> ScanResult:
    r = ScanResult(repo_path='/repo')
    r.scanned_count = 10
    r.add(Gap(kind='MISSING_COMPANION', path='/repo/a.py', rel_path='a.py'))
    r.add(Gap(kind='MISSING_COMPANION', path='/repo/b.py', rel_path='b.py'))
    r.add(Gap(kind='MISSING_HEADER', path='/repo/c.py', rel_path='c.py', detail='c (line 1)'))
    return r

def _make_sprint(overall: float=50.0, remaining: int=5) -> SprintReport:
    return SprintReport(sprint_repo_path='/repo', source_files=10, with_doc_md=5, with_purpose_header=5, public_funcs=4, public_funcs_with_doc=2, overall_pct=overall, doc_md_pct=50.0, header_pct=50.0, docstring_pct=50.0, comment_density_pct=10.0, sprint_files_remaining=remaining, sprint_header_remaining=remaining, sprint_runtime_seconds=0.42)

class TestFormatGapTable(unittest.TestCase):

    def test_includes_all_kinds(self):
        """Gap table mentions every kind."""
        out = format_gap_table(_make_result())
        for kind in ('MISSING_COMPANION', 'MISSING_HEADER', 'MISSING_DOCSTRING'):
            self.assertIn(kind, out)

    def test_shows_totals(self):
        """Gap table shows the total row."""
        out = format_gap_table(_make_result())
        self.assertIn('Source files scanned', out)
        self.assertIn('TOTAL', out)

    def test_error_path(self):
        """An error result renders the error string."""
        r = ScanResult(repo_path='/x')
        r.error = 'boom'
        self.assertIn('boom', format_gap_table(r))

class TestFormatGapListing(unittest.TestCase):

    def test_groups_by_kind(self):
        """Gap listing groups items by kind."""
        out = format_gap_listing(_make_result())
        self.assertIn('MISSING_COMPANION', out)
        self.assertIn('MISSING_HEADER', out)
        self.assertIn('a.py', out)
        self.assertIn('b.py', out)
        self.assertIn('c.py', out)

    def test_caps_long_listings(self):
        """max_lines truncates the listing with a footer."""
        r = ScanResult(repo_path='/x')
        r.scanned_count = 300
        for i in range(300):
            r.add(Gap(kind='MISSING_COMPANION', path=f'/x/f{i}.py', rel_path=f'f{i}.py'))
        out = format_gap_listing(r, max_lines=10)
        self.assertIn('and 290 more', out)

    def test_no_gaps_message(self):
        """Empty gap list prints a 100% message."""
        r = ScanResult(repo_path='/x')
        r.scanned_count = 0
        out = format_gap_listing(r)
        self.assertIn('100%', out)

class TestFormatSprintSummary(unittest.TestCase):

    def test_includes_coverage_and_gaps(self):
        """Sprint summary includes both axes."""
        out = format_sprint_summary(_make_sprint())
        for k in ('Overall coverage', '.doc.md coverage', 'Files needing'):
            self.assertIn(k, out)

    def test_error_path(self):
        """Sprint summary renders the error string."""
        sp = SprintReport(sprint_error='upstream missing')
        self.assertIn('upstream missing', format_sprint_summary(sp))

class TestFormatDiff(unittest.TestCase):

    def test_shows_before_after(self):
        """Diff shows before/after with sign convention."""
        before = _make_sprint(overall=30.0, remaining=10)
        after = _make_sprint(overall=80.0, remaining=2)
        out = format_diff(before, after)
        self.assertIn('BEFORE', out)
        self.assertIn('AFTER', out)
        self.assertIn('Overall %', out)
        self.assertIn('+50', out)
        self.assertIn('-8', out)
if __name__ == '__main__':
    unittest.main()
