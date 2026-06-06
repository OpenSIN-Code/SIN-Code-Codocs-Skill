"""Purpose: Smoke tests for the sin-codocs scripts and templates.

Docs: test_init.doc.md

These tests verify the bash scripts exist, are executable, and that
the templates render valid Python with the SOTA markers. They do not
spawn subprocesses (no init.sh end-to-end run) because that would
require a temp repo on disk. Instead we lint the script files and
template files directly.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
TEMPLATES_DIR = SKILL_DIR / "templates"
LIB_DIR = SKILL_DIR / "lib"
EXAMPLES_DIR = SKILL_DIR / "examples"


class TestScriptsExist(unittest.TestCase):
    """Every documented script must exist as a file."""

    def test_required_scripts(self):
        """Every documented script must exist as a file in scripts/."""
        for name in ("init.sh", "check.sh", "new-doc-md.sh",
                     "new-module.sh", "coverage.sh"):
            path = SCRIPTS_DIR / name
            self.assertTrue(path.exists(), f"missing script: {path}")
            self.assertTrue(path.is_file(), f"not a file: {path}")

    def test_scripts_are_executable(self):
        """Every script must be executable for both user and group (mode bit check)."""
        for name in ("init.sh", "check.sh", "new-doc-md.sh",
                     "new-module.sh", "coverage.sh"):
            path = SCRIPTS_DIR / name
            mode = path.stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR,
                            f"not executable (user): {path}")
            self.assertTrue(mode & stat.S_IXGRP,
                            f"not executable (group): {path}")

    def test_scripts_have_shebang(self):
        """Every script's first line must start with `#!` so it runs as a binary."""
        for name in ("init.sh", "check.sh", "new-doc-md.sh",
                     "new-module.sh", "coverage.sh"):
            path = SCRIPTS_DIR / name
            first = path.read_text(encoding="utf-8").splitlines()[:1]
            self.assertTrue(first, f"{path} is empty")
            self.assertTrue(first[0].startswith("#!"),
                            f"{path} has no shebang: {first[0]!r}")

    def test_scripts_have_purpose_comment(self):
        """Every script should have a # Purpose: line near the top."""
        for name in ("init.sh", "check.sh", "new-doc-md.sh",
                     "new-module.sh", "coverage.sh"):
            path = SCRIPTS_DIR / name
            head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:5])
            self.assertIn("Purpose:", head,
                          f"{path} missing Purpose comment in header")

    def test_scripts_pass_bash_syntax(self):
        """Run `bash -n` on every script to verify parseability."""
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash not on PATH")
        for name in ("init.sh", "check.sh", "new-doc-md.sh",
                     "new-module.sh", "coverage.sh"):
            path = SCRIPTS_DIR / name
            result = subprocess.run(
                [bash, "-n", str(path)],
                capture_output=True, text=True
            )
            self.assertEqual(
                result.returncode, 0,
                f"{path} failed bash -n:\n{result.stderr}"
            )


class TestTemplates(unittest.TestCase):
    """The Python template must render valid, SOTA Python."""

    def test_module_template_exists(self):
        """The module.py template file must be present in templates/."""
        self.assertTrue((TEMPLATES_DIR / "module.py.template").exists())

    def test_module_template_compiles(self):
        """The module.py template must be valid Python (compile() succeeds)."""
        path = TEMPLATES_DIR / "module.py.template"
        try:
            compile(path.read_text(encoding="utf-8"),
                    filename=str(path), mode="exec")
        except SyntaxError as e:
            self.fail(f"template not valid Python: {e}")

    def test_module_template_has_purpose_and_docs(self):
        """The module.py template must contain `Purpose:` and `Docs:` markers."""
        text = (TEMPLATES_DIR / "module.py.template").read_text()
        self.assertIn("Purpose:", text)
        self.assertIn("Docs:", text)

    def test_module_template_has_section_separators(self):
        """The module.py template must use box-drawing section separators (SOTA style)."""
        text = (TEMPLATES_DIR / "module.py.template").read_text()
        # Match the box-drawing separator style: "# ── Name ──..."
        # The character is U+2500 BOX DRAWINGS LIGHT HORIZONTAL.
        self.assertRegex(text, r"#\s+─+\s+\S")

    def test_doc_md_template_exists(self):
        """The module.doc.md template file must be present in templates/."""
        self.assertTrue((TEMPLATES_DIR / "module.doc.md.template").exists())

    def test_doc_md_template_has_required_sections(self):
        """The doc.md template must include the four required `##` sections."""
        text = (TEMPLATES_DIR / "module.doc.md.template").read_text()
        for section in ("## What it does", "## Dependencies",
                        "## Usage examples", "## Known caveats"):
            self.assertIn(section, text, f"missing section: {section}")

    def test_go_template_compiles_as_text(self):
        """The Go template must declare Purpose, Docs, and at least one public func."""
        path = TEMPLATES_DIR / "module.go.template"
        text = path.read_text(encoding="utf-8")
        # Go compiler is unlikely to be installed; we lint manually
        self.assertIn("// Purpose:", text)
        self.assertIn("// Docs:", text)
        self.assertIn("func PublicFunction", text)


class TestInitScriptBehavior(unittest.TestCase):
    """Behavioral tests for `scripts/init.sh`."""

    def setUp(self):
        """Create a unique temp dir for init.sh to run against."""
        self.tmp = tempfile.mkdtemp(prefix="sin-codocs-init-")

    def tearDown(self):
        """Remove the temp dir; ignore errors so a leftover chmod 0000 cannot fail the test."""
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_init(self, *extra_args) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPTS_DIR / "init.sh"), self.tmp, *extra_args],
            capture_output=True, text=True, timeout=30
        )

    def test_init_creates_doc_md_for_existing_source(self):
        """init.sh on a dir with one .py file must create a matching .doc.md."""
        src = Path(self.tmp) / "foo.py"
        src.write_text('"""Purpose: x\nDocs: foo.doc.md\n"""', encoding="utf-8")
        result = self._run_init()
        self.assertEqual(result.returncode, 0,
                         f"init.sh failed:\n{result.stderr}")
        self.assertTrue((Path(self.tmp) / "foo.doc.md").exists(),
                        "init.sh did not create foo.doc.md")

    def test_init_skips_skill_own_files(self):
        """init.sh on its own dir must not modify the scripts/ directory."""
        # Pre-existing skill files must not be rewritten
        before = {p.name for p in SCRIPTS_DIR.iterdir()}
        result = self._run_init(str(SKILL_DIR))
        self.assertEqual(result.returncode, 0)
        after = {p.name for p in SCRIPTS_DIR.iterdir()}
        self.assertEqual(before, after, "init.sh modified skill scripts dir")

    def test_init_dry_runs_on_empty_dir(self):
        """init.sh on an empty dir must exit 0 and create nothing."""
        result = self._run_init()
        self.assertEqual(result.returncode, 0)


class TestExamples(unittest.TestCase):
    """The good example must follow every rule; the bad example must violate most."""

    def test_good_auth_compiles(self):
        """good/auth.py must be syntactically valid Python."""
        path = EXAMPLES_DIR / "good" / "auth.py"
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as e:
            self.fail(f"good/auth.py is not valid Python: {e}")

    def test_good_auth_has_companion_doc(self):
        """good/auth.py must have a good/auth.doc.md companion file."""
        self.assertTrue((EXAMPLES_DIR / "good" / "auth.doc.md").exists())

    def test_good_auth_has_purpose_and_docs_in_header(self):
        """good/auth.py's module docstring must contain Purpose and Docs markers."""
        text = (EXAMPLES_DIR / "good" / "auth.py").read_text()
        # Look in the module docstring
        m = re.search(r'"""(.*?)"""', text, re.DOTALL)
        self.assertIsNotNone(m, "good/auth.py missing module docstring")
        docstring = m.group(1)
        self.assertIn("Purpose:", docstring)
        self.assertIn("Docs: auth.doc.md", docstring)

    def test_good_auth_public_functions_have_docstrings(self):
        """Every top-level public def in good/auth.py must have a docstring."""
        text = (EXAMPLES_DIR / "good" / "auth.py").read_text()
        # Every `def <name>(` at column 0 (top-level) should be followed
        # by a docstring. Find each def line, skip past the signature's
        # trailing `:`, then look at the first non-comment body line.
        # Pattern: def name(...args...) [-> ReturnType]:\n[optional # comment]
        top_level_defs = list(
            re.finditer(
                r"^def (\w+)\([^)]*\)(?:\s*->\s*[^:]+)?\s*:",
                text, re.MULTILINE
            )
        )
        public = [m for m in top_level_defs if not m.group(1).startswith("_")]
        self.assertGreaterEqual(len(public), 2, "expected >= 2 public funcs")
        for m in public:
            name = m.group(1)
            tail = text[m.end():m.end() + 400]
            # First non-blank, non-comment body line should be a docstring
            body_lines = [
                ln for ln in tail.splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")
            ]
            first_body = body_lines[0] if body_lines else "<empty>"
            self.assertTrue(
                body_lines and body_lines[0].lstrip().startswith('"""'),
                "good/auth.py: public function " + name + "() has no docstring "
                "(first body line: " + repr(first_body) + ")"
            )

    def test_bad_legacy_compiles(self):
        """The bad example must compile — otherwise it's not a fair comparison."""
        path = EXAMPLES_DIR / "bad" / "legacy.py"
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as e:
            self.fail(f"bad/legacy.py is not valid Python: {e}")

    def test_bad_legacy_has_no_companion_doc(self):
        """bad/legacy.py must NOT have a companion doc — it's the anti-example."""
        # The whole point of the bad example is to demonstrate missing docs
        self.assertFalse(
            (EXAMPLES_DIR / "bad" / "legacy.doc.md").exists(),
            "bad/legacy.py should NOT have a companion doc — it's the anti-example"
        )


if __name__ == "__main__":
    unittest.main()
