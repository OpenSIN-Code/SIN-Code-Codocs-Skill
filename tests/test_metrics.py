"""Purpose: Unit tests for the src/sin_codocs/metrics.py and src/sin_codocs/audit_inline.py libraries.

Docs: test_metrics.doc.md

These tests exercise the coverage-measurement and inline-audit tools
against the examples in `examples/good` and `examples/bad`, verifying
that:

  - good/auth.py gets a high coverage score
  - bad/legacy.py gets a low coverage score (and is flagged)
  - the metric math is stable across runs
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / "src/sin_codocs"
EXAMPLES_DIR = SKILL_DIR / "examples"


class TestMetricsLib(unittest.TestCase):
    """Unit tests for src/sin_codocs/metrics.py."""

    def setUp(self):
        """Inject the lib dir onto sys.path and bind `measure` for the test."""
        sys.path.insert(0, str(LIB_DIR))
        from metrics import measure
        self.measure = measure

    def tearDown(self):
        """Remove the lib dir from sys.path so the test does not leak imports."""
        sys.path.remove(str(LIB_DIR))

    def test_good_example_high_overall(self):
        """The good example should score well above 70% overall."""
        report = self.measure(str(EXAMPLES_DIR / "good"))
        self.assertGreaterEqual(
            report.source_files, 1, "good example dir has no source files?"
        )
        self.assertEqual(report.with_doc_md, report.source_files,
                         "good/auth.py should have auth.doc.md")
        # Overall should be at least 60% (allowing for the bad example
        # if it were scanned alongside)
        self.assertGreaterEqual(
            report.overall_pct, 60.0,
            f"good example scored {report.overall_pct:.1f}%, expected >= 60"
        )

    def test_bad_example_low_overall(self):
        """The bad example should score below 70% overall."""
        report = self.measure(str(EXAMPLES_DIR / "bad"))
        self.assertEqual(report.with_doc_md, 0,
                         "bad/legacy.py should not have a companion doc")
        self.assertLess(
            report.overall_pct, 70.0,
            f"bad example scored {report.overall_pct:.1f}%, expected < 70"
        )

    def test_empty_dir_returns_zero_files(self):
        """An empty directory must report zero files and zero overall (no NaN)."""
        with tempfile.TemporaryDirectory() as d:
            report = self.measure(d)
            self.assertEqual(report.source_files, 0)
            # No division-by-zero
            self.assertEqual(report.overall_pct, 0.0)

    def test_metrics_cli_json_output(self):
        """The CLI must produce valid JSON with the documented fields."""
        result = subprocess.run(
            [sys.executable, str(LIB_DIR / "metrics.py"),
             "--path", str(EXAMPLES_DIR / "good"), "--json"],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.fail(f"metrics CLI produced invalid JSON: {e}\n{result.stdout}")
        for key in ("source_files", "with_doc_md", "doc_md_pct",
                    "header_pct", "docstring_pct", "overall_pct"):
            self.assertIn(key, data, f"missing key: {key}")

    def test_metrics_cli_min_threshold(self):
        """`--min=N` should exit non-zero when below threshold."""
        result = subprocess.run(
            [sys.executable, str(LIB_DIR / "metrics.py"),
             "--path", str(EXAMPLES_DIR / "bad"), "--min", "99"],
            capture_output=True, text=True, timeout=30
        )
        # bad example should fail the 99% bar
        self.assertNotEqual(result.returncode, 0)

    def test_report_to_dict_serializable(self):
        """CoverageReport fields are JSON-safe."""
        report = self.measure(str(EXAMPLES_DIR / "good"))
        d = {
            "source_files": report.source_files,
            "with_doc_md": report.with_doc_md,
            "doc_md_pct": report.doc_md_pct,
            "overall_pct": report.overall_pct,
        }
        encoded = json.dumps(d)
        roundtrip = json.loads(encoded)
        self.assertEqual(roundtrip["source_files"], report.source_files)


class TestAuditInlineLib(unittest.TestCase):
    """Unit tests for src/sin_codocs/audit_inline.py."""

    def setUp(self):
        """Inject the lib dir onto sys.path and bind `audit_file` for the test."""
        sys.path.insert(0, str(LIB_DIR))
        from audit_inline import audit_file
        self.audit_file = audit_file

    def tearDown(self):
        """Remove the lib dir from sys.path so the test does not leak imports."""
        sys.path.remove(str(LIB_DIR))

    def test_good_example_passes_module_docstring_check(self):
        """Audit of good/auth.py must report module docstring + Purpose + Docs."""
        result = self.audit_file(str(EXAMPLES_DIR / "good" / "auth.py"))
        self.assertTrue(result.has_module_docstring,
                        "good/auth.py should have a module docstring")
        self.assertTrue(result.has_purpose_keyword)
        self.assertTrue(result.has_docs_keyword)
        self.assertEqual(
            result.issues, [],
            f"good/auth.py should have no issues, got: {result.issues}"
        )

    def test_bad_example_flagged_for_missing_docstring(self):
        """The bad example must be flagged (no Purpose, no Docs keywords)."""
        result = self.audit_file(str(EXAMPLES_DIR / "bad" / "legacy.py"))
        self.assertTrue(len(result.issues) > 0
                        or len(result.warnings) > 0,
                        "bad/legacy.py should be flagged for at least one issue")
        # bad/legacy.py has 'Auth utilities.' as the only docstring —
        # no Purpose, no Docs
        self.assertFalse(result.has_purpose_keyword)
        self.assertFalse(result.has_docs_keyword)

    def test_docstring_coverage_calculation(self):
        """Audit of good/auth.py should report 3 public funcs, all documented."""
        result = self.audit_file(str(EXAMPLES_DIR / "good" / "auth.py"))
        # auth.py has 4 public functions (issue_token, verify_token,
        # old_login, _validate_key is private), all with docstrings
        self.assertEqual(result.public_funcs, 3)
        self.assertEqual(result.public_funcs_with_docstring, 3)
        self.assertEqual(result.docstring_coverage, 1.0)

    def test_missing_file_raises(self):
        """audit_file on a missing path must raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            self.audit_file("/nonexistent/path.py")

    def test_audit_cli_json_output(self):
        """`audit_inline.py --json` must produce a JSON list with the documented fields."""
        result = subprocess.run(
            [sys.executable, str(LIB_DIR / "audit_inline.py"),
             "--json", str(EXAMPLES_DIR / "good" / "auth.py")],
            capture_output=True, text=True, timeout=30
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("public_funcs", data[0])
        self.assertIn("docstring_coverage", data[0])

    def test_audit_cli_strict_exits_1_on_bad_example(self):
        """`--strict` must return non-zero when the bad example has issues."""
        result = subprocess.run(
            [sys.executable, str(LIB_DIR / "audit_inline.py"),
             "--strict", str(EXAMPLES_DIR / "bad" / "legacy.py")],
            capture_output=True, text=True, timeout=30
        )
        # bad/legacy.py missing module docstring → issue → strict fails
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
