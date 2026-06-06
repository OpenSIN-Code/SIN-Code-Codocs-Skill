"""Purpose: Unit tests for the scanner.

Docs: test_scanner.doc.md

Tests the gap detection against small synthesized repos, verifying:

  - MISSING_COMPANION is detected
  - MISSING_HEADER is detected
  - MISSING_DOCSTRING is detected (Python public funcs only)
  - Clean files generate zero gaps
  - SKIP_DIRS are honored
  - Multi-language extension support works
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / 'scripts'
LIB_DIR = SKILL_DIR / 'src/sin_codocs'
sys.path.insert(0, str(SKILL_DIR / 'src'))
from sin_codocs.scanner import scan_repo, ScanResult, Gap

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding='utf-8')

class TestScanRepo(unittest.TestCase):
    """End-to-end scan tests with synthesized repos."""

    def setUp(self):
        """Set up a temp dir for the test."""
        self.tmp = tempfile.mkdtemp(prefix='sprint-scan-')

    def tearDown(self):
        """Remove the temp dir."""
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_dir_has_no_gaps(self):
        """An empty repo scans to zero gaps."""
        result = scan_repo(self.tmp)
        self.assertFalse(result.has_gaps)
        self.assertEqual(result.scanned_count, 0)

    def test_missing_dir_sets_error(self):
        """A non-existent path sets the result.error field."""
        result = scan_repo('/nonexistent/path/xyz')
        self.assertTrue(result.error)
        self.assertEqual(result.scanned_count, 0)

    def test_detects_missing_companion(self):
        """A file with no .doc.md sibling is flagged MISSING_COMPANION."""
        _write(Path(self.tmp) / 'foo.py', 'def foo(): pass\n')
        result = scan_repo(self.tmp)
        self.assertEqual(result.scanned_count, 1)
        kinds = {g.kind for g in result.gaps}
        self.assertIn('MISSING_COMPANION', kinds)
        self.assertEqual(result.by_kind['MISSING_COMPANION'], 1)

    def test_detects_missing_header(self):
        """A file lacking Purpose/Docs is flagged MISSING_HEADER."""
        _write(Path(self.tmp) / 'bar.py', 'def bar(): pass\n')
        result = scan_repo(self.tmp)
        header_gaps = [g for g in result.gaps if g.kind == 'MISSING_HEADER']
        self.assertEqual(len(header_gaps), 1)
        self.assertEqual(header_gaps[0].rel_path, 'bar.py')

    def test_clean_file_has_no_gaps(self):
        """A fully-documented file produces zero gaps."""
        _write(Path(self.tmp) / 'good.py', '        """Purpose: A clean file.\n\n        Docs: good.doc.md\n        """\n\n\n        def hello():\n            """Say hi."""\n            return "hi"\n        ')
        _write(Path(self.tmp) / 'good.doc.md', '# good.py\n\n**Purpose:** A clean file.\n')
        result = scan_repo(self.tmp)
        self.assertFalse(result.has_gaps, f'unexpected gaps: {[g.kind for g in result.gaps]}')

    def test_detects_missing_docstring(self):
        """Public functions without docstrings are flagged MISSING_DOCSTRING."""
        _write(Path(self.tmp) / 'doc.py', '        """Purpose: x\n\n        Docs: doc.doc.md\n        """\n\n\n        def public_one():\n            return 1\n\n\n        def public_two():\n            return 2\n        ')
        _write(Path(self.tmp) / 'doc.doc.md', '# x\n')
        result = scan_repo(self.tmp)
        ds = [g for g in result.gaps if g.kind == 'MISSING_DOCSTRING']
        self.assertEqual(len(ds), 2, f'expected 2 docstring gaps, got {len(ds)}')
        names = {g.detail.split(' ')[0] for g in ds}
        self.assertIn('public_one', names)
        self.assertIn('public_two', names)

    def test_skips_private_functions(self):
        """Private functions (underscore prefix) are skipped."""
        _write(Path(self.tmp) / 'priv.py', '        """Purpose: x\n\n        Docs: priv.doc.md\n        """\n\n\n        def _private():\n            return 1\n        ')
        _write(Path(self.tmp) / 'priv.doc.md', '# x\n')
        result = scan_repo(self.tmp)
        ds = [g for g in result.gaps if g.kind == 'MISSING_DOCSTRING']
        self.assertEqual(len(ds), 0, 'private functions should not be flagged')

    def test_skips_junk_dirs(self):
        """.venv, node_modules, etc. are skipped."""
        _write(Path(self.tmp) / '.venv' / 'lib.py', 'x = 1\n')
        _write(Path(self.tmp) / 'node_modules' / 'lib.py', 'x = 1\n')
        _write(Path(self.tmp) / 'src' / 'real.py', 'def real(): pass\n')
        result = scan_repo(self.tmp)
        self.assertEqual(result.scanned_count, 1)
        paths = [g.rel_path for g in result.gaps]
        self.assertTrue(any(('real.py' in p for p in paths)))
        self.assertFalse(any(('.venv' in p for p in paths)))
        self.assertFalse(any(('node_modules' in p for p in paths)))

    def test_supports_multiple_languages(self):
        """TS, Go, Rust, JS files are scanned too."""
        _write(Path(self.tmp) / 'a.ts', 'export const x = 1\n')
        _write(Path(self.tmp) / 'b.go', 'package x\n')
        _write(Path(self.tmp) / 'c.rs', 'fn main() {}\n')
        _write(Path(self.tmp) / 'd.js', 'module.exports = 1\n')
        result = scan_repo(self.tmp)
        self.assertEqual(result.scanned_count, 4)
        self.assertEqual(result.by_kind['MISSING_COMPANION'], 4)

    def test_suggested_doc_path(self):
        """suggested_doc field ends with the .doc.md filename."""
        _write(Path(self.tmp) / 'alpha.py', 'x = 1\n')
        result = scan_repo(self.tmp)
        companion_gaps = [g for g in result.gaps if g.kind == 'MISSING_COMPANION']
        self.assertEqual(len(companion_gaps), 1)
        self.assertTrue(companion_gaps[0].suggested_doc.endswith('alpha.doc.md'))

class TestScannerCLI(unittest.TestCase):
    """Verify the CLI wraps the lib correctly."""

    def setUp(self):
        """Set up a temp dir for the CLI tests."""
        self.tmp = tempfile.mkdtemp(prefix='sprint-scan-cli-')

    def tearDown(self):
        """Remove the temp dir."""
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_json_output(self):
        """CLI --json produces the documented schema."""
        _write(Path(self.tmp) / 'one.py', 'x = 1\n')
        proc = subprocess.run([sys.executable, str(LIB_DIR / 'scanner.py'), '--path', self.tmp, '--json'], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        for key in ('repo_path', 'scanned_count', 'by_kind', 'gaps'):
            self.assertIn(key, data)

    def test_kind_filter(self):
        """CLI --kind filters the gap list."""
        _write(Path(self.tmp) / 'two.py', 'x = 1\n')
        proc = subprocess.run([sys.executable, str(LIB_DIR / 'scanner.py'), '--path', self.tmp, '--json', '--kind', 'MISSING_COMPANION'], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        for g in data['gaps']:
            self.assertEqual(g['kind'], 'MISSING_COMPANION')
if __name__ == '__main__':
    unittest.main()
