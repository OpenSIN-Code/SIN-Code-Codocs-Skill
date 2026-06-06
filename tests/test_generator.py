"""Purpose: Unit tests for the generator.

Docs: test_generator.doc.md

Tests the draft `.doc.md` rendering pipeline:

  - extract_facts() picks up Purpose from a header
  - extract_facts() picks up imports / public_funcs / constants
  - generate_draft() substitutes the template correctly
  - write_draft() refuses to overwrite (unless forced)
  - The CLI is the same shape as the public API
"""
from __future__ import annotations
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
SKILL_DIR = Path(__file__).resolve().parent.parent
LIB_DIR = SKILL_DIR / 'src/sin_codocs'
sys.path.insert(0, str(SKILL_DIR / 'src'))
from sin_codocs.generator import generate_draft, write_draft, extract_facts, SourceFacts

def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding='utf-8')

class TestExtractFacts(unittest.TestCase):
    """Tests for the auto-fillable fact extraction."""

    def test_purpose_from_header(self):
        """extract_facts picks up the Purpose: line."""
        facts = extract_facts_for('\n        # Purpose: short description here\n        # Docs: foo.doc.md\n        def x(): pass\n        ', 'foo.py')
        self.assertEqual(facts.purpose, 'short description here')
        self.assertEqual(facts.filename, 'foo.py')

    def test_purpose_from_python_docstring(self):
        """Falls back to the docstring's first line."""
        facts = extract_facts_for('\n        """Purpose: docstring purpose.\n\n        Docs: foo.doc.md\n        """\n        ', 'foo.py')
        self.assertIn('docstring purpose', facts.purpose)

    def test_imports_extracted(self):
        """All import lines are captured."""
        facts = extract_facts_for('\n        """Purpose: x\n\n        Docs: foo.doc.md\n        """\n        import os\n        import json\n        from pathlib import Path\n        ', 'foo.py')
        self.assertGreaterEqual(len(facts.imports), 3)
        self.assertTrue(any(('os' in i for i in facts.imports)))
        self.assertTrue(any(('pathlib' in i.lower() for i in facts.imports)))

    def test_public_funcs_extracted(self):
        """All public defs are captured; private ones are skipped."""
        facts = extract_facts_for('\n        """Purpose: x\n\n        Docs: foo.doc.md\n        """\n        def alpha(): pass\n        def beta(): pass\n        def _private(): pass\n        ', 'foo.py')
        names = [n.split('(')[0] for n in facts.public_funcs]
        self.assertIn('alpha', names)
        self.assertIn('beta', names)
        self.assertNotIn('_private', names)

    def test_constants_extracted(self):
        """Module-level numeric + string constants are captured."""
        facts = extract_facts_for('\n        """Purpose: x\n\n        Docs: foo.doc.md\n        """\n        MAX_RETRIES = 3\n        NAME = "foo"\n        ', 'foo.py')
        names = [c[0] for c in facts.constants]
        self.assertIn('MAX_RETRIES', names)
        self.assertIn('NAME', names)

class TestGenerateDraft(unittest.TestCase):
    """Tests for the template rendering."""

    def test_basic_substitution(self):
        """Template placeholders are filled in."""
        facts = SourceFacts(filename='alpha.py', purpose='Compute stuff', header_excerpt='"""Purpose: Compute stuff\n\nDocs: alpha.doc.md\n"""', imports=['import os'], public_funcs=['run()'], constants=[('MAX', '10')])
        text = generate_draft(Path('unused'), facts=facts)
        self.assertIn('alpha.py', text)
        self.assertIn('Compute stuff', text)
        self.assertIn('alpha.doc.md', text)
        self.assertIn('os', text)
        self.assertIn('run', text)
        self.assertIn('MAX', text)

    def test_purpose_fallback(self):
        """Missing purpose renders as a TODO placeholder."""
        facts = SourceFacts(filename='x.py', purpose='')
        text = generate_draft(Path('unused'), facts=facts)
        self.assertIn('TODO', text)

    def test_missing_imports_shows_placeholder(self):
        """Empty imports list shows a template example."""
        facts = SourceFacts(filename='x.py', purpose='p')
        text = generate_draft(Path('unused'), facts=facts)
        self.assertIn('TODO', text)
        self.assertIn('module.a', text)

class TestWriteDraft(unittest.TestCase):
    """Tests for the writer's safety rails."""

    def setUp(self):
        """Set up a temp dir for the writer tests."""
        self.tmp = tempfile.mkdtemp(prefix='sprint-gen-')

    def tearDown(self):
        """Remove the temp dir."""
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_new_file(self):
        """write_draft creates a .doc.md next to the source."""
        src = Path(self.tmp) / 'new.py'
        src.write_text('"""Purpose: x\n\nDocs: new.doc.md\n"""\n')
        path = write_draft(src)
        self.assertTrue(path.exists())
        self.assertIn('DRAFT', path.read_text())

    def test_refuses_to_overwrite(self):
        """Existing .doc.md is not clobbered."""
        src = Path(self.tmp) / 'k.py'
        src.write_text('"""Purpose: x\n\nDocs: k.doc.md\n"""\n')
        doc = src.with_name('k.doc.md')
        doc.write_text('# existing\n')
        with self.assertRaises(FileExistsError):
            write_draft(src)
        self.assertEqual(doc.read_text(), '# existing\n')

    def test_overwrite_with_flag(self):
        """overwrite=True clobbers an existing .doc.md."""
        src = Path(self.tmp) / 'k.py'
        src.write_text('"""Purpose: x\n\nDocs: k.doc.md\n"""\n')
        doc = src.with_name('k.doc.md')
        doc.write_text('# old\n')
        path = write_draft(src, overwrite=True)
        self.assertIn('DRAFT', path.read_text())

    def test_raises_on_missing_source(self):
        """Missing source file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            write_draft(Path('/no/such/file.py'))

class TestGeneratorCLI(unittest.TestCase):
    """Verify the CLI output is consistent with the public API."""

    def setUp(self):
        """Set up a temp dir for the CLI tests."""
        self.tmp = tempfile.mkdtemp(prefix='sprint-gen-cli-')

    def tearDown(self):
        """Remove the temp dir."""
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stdout_flag(self):
        """--stdout writes to stdout, not disk."""
        src = Path(self.tmp) / 'c.py'
        src.write_text('"""Purpose: c\n\nDocs: c.doc.md\n"""\n')
        proc = subprocess.run([sys.executable, str(LIB_DIR / 'generator.py'), str(src), '--stdout'], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('c.py', proc.stdout)
        self.assertIn('DRAFT', proc.stdout)

    def test_writes_when_no_stdout(self):
        """Default behavior writes the .doc.md to disk."""
        src = Path(self.tmp) / 'w.py'
        src.write_text('"""Purpose: w\n\nDocs: w.doc.md\n"""\n')
        proc = subprocess.run([sys.executable, str(LIB_DIR / 'generator.py'), str(src)], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((Path(self.tmp) / 'w.doc.md').exists())

def extract_facts_for(content: str, filename: str) -> SourceFacts:
    """Write content to a tmp file, then run extract_facts on it."""
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix=filename, delete=False) as f:
        f.write(textwrap.dedent(content))
        tmp_path = Path(f.name)
    try:
        tmp_path = tmp_path.with_name(filename)
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(textwrap.dedent(content), encoding='utf-8')
        return extract_facts(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
if __name__ == '__main__':
    unittest.main()
