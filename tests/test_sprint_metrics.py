"""Purpose: Tests for the metrics wrapper + integration with the upstream.

Docs: test_metrics.doc.md

Verifies that:
  - run_sprint_metrics() returns a SprintReport populated from upstream
  - subprocess failure (missing upstream) is surfaced via sprint_error
  - JSON CLI output matches the documented schema
  - run_sprint_metrics adds the sprint-specific derived fields correctly
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / 'src/sin_codocs'
UPSTREAM_LIB = Path.home() / '.config/opencode/skills/sin-codocs/src/sin_codocs/metrics.py'
sys.path.insert(0, str(SKILL_DIR / 'src'))
from sin_codocs.sprint_metrics import run_sprint_metrics, SprintReport

class TestRunSprintMetrics(unittest.TestCase):
    """Tests for the public API."""

    def setUp(self):
        """Set up a temp dir for the metrics tests."""
        self.tmp = tempfile.mkdtemp(prefix='sprint-metrics-')

    def tearDown(self):
        """Remove the temp dir."""
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_python_file(self, name: str, with_doc: bool=False) -> None:
        p = Path(self.tmp) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if with_doc:
            p.write_text('"""Purpose: x\n\nDocs: ' + name + '.doc.md\n"""\ndef hello(): return 1\n', encoding='utf-8')
            (p.parent / (p.stem + '.doc.md')).write_text('# x\n')
        else:
            p.write_text('def hello(): return 1\n', encoding='utf-8')

    def test_basic_report_shape(self):
        """Real upstream produces a populated SprintReport."""
        self._make_python_file('a.py')
        self._make_python_file('b.py', with_doc=True)
        if not UPSTREAM_LIB.exists():
            self.skipTest(f'upstream sin-codocs not installed: {UPSTREAM_LIB}')
        report = run_sprint_metrics(self.tmp)
        self.assertEqual(report.sprint_error, '')
        self.assertEqual(report.source_files, 2)
        self.assertEqual(report.with_doc_md, 1)
        self.assertEqual(report.sprint_files_remaining, 1)
        self.assertGreaterEqual(report.overall_pct, 0)
        self.assertLessEqual(report.overall_pct, 100)

    def test_derived_fields(self):
        """Sprint-specific fields are derived correctly."""
        self._make_python_file('x.py')
        if not UPSTREAM_LIB.exists():
            self.skipTest(f'upstream sin-codocs not installed: {UPSTREAM_LIB}')
        report = run_sprint_metrics(self.tmp)
        self.assertEqual(report.sprint_files_remaining, report.source_files - report.with_doc_md)
        self.assertEqual(report.sprint_header_remaining, report.source_files - report.with_purpose_header)
        self.assertGreaterEqual(report.sprint_runtime_seconds, 0)

    def test_missing_upstream_sets_error(self, monkeymethod=None):
        """A missing upstream path sets sprint_error."""
        import sin_codocs.sprint_metrics as metrics
        original = metrics.SINCODOCS_METRICS
        metrics.SINCODOCS_METRICS = Path('/no/such/file.py')
        try:
            report = run_sprint_metrics(self.tmp)
            self.assertNotEqual(report.sprint_error, '')
            self.assertEqual(report.source_files, 0)
            self.assertEqual(report.overall_pct, 0.0)
        finally:
            metrics.SINCODOCS_METRICS = original

class TestMetricsCLI(unittest.TestCase):
    """Tests for the CLI shape."""

    def setUp(self):
        """Set up a temp dir for the CLI tests."""
        self.tmp = tempfile.mkdtemp(prefix='sprint-metrics-cli-')

    def tearDown(self):
        """Remove the temp dir."""
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_json_output_shape(self):
        """CLI JSON has all upstream + sprint fields."""
        (Path(self.tmp) / 'x.py').write_text('def x(): pass\n', encoding='utf-8')
        proc = subprocess.run([sys.executable, str(LIB_DIR / 'sprint_metrics.py'), '--path', self.tmp, '--json'], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode in (0, 1), True, proc.stderr)
        data = json.loads(proc.stdout)
        for key in ('source_files', 'with_doc_md', 'doc_md_pct', 'overall_pct'):
            self.assertIn(key, data, f'missing upstream field: {key}')
        for key in ('sprint_repo_path', 'sprint_files_remaining', 'sprint_header_remaining', 'sprint_runtime_seconds'):
            self.assertIn(key, data, f'missing sprint field: {key}')

    def test_min_threshold_exit_code(self):
        """--min gate produces a non-2 exit code."""
        proc = subprocess.run([sys.executable, str(LIB_DIR / 'sprint_metrics.py'), '--path', self.tmp, '--min', '50'], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(proc.returncode, 2)
if __name__ == '__main__':
    unittest.main()
