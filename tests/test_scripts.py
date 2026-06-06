"""Purpose: Smoke tests for the sin-codocs-sprint scripts and templates.

Docs: test_scripts.doc.md

Verifies that:
  - Every documented script exists, is executable, has a shebang,
    and has a `Purpose:` header.
  - Every script passes `bash -n` (no syntax errors).
  - Every template exists.
  - The scan.sh / generate.sh / status.sh / diff.sh / sprint.sh
    smoke tests pass on a synthesized tiny repo.
"""
from __future__ import annotations
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / 'scripts'
TEMPLATES_DIR = SKILL_DIR / 'templates'
LIB_DIR = SKILL_DIR / 'lib'

class TestScriptsExist(unittest.TestCase):

    def test_required_scripts(self):
        """All 6 documented scripts exist."""
        for name in ('sprint.sh', 'scan.sh', 'generate.sh', 'diff.sh', 'status.sh', 'install-skill.sh'):
            path = SCRIPTS_DIR / name
            self.assertTrue(path.exists(), f'missing script: {path}')
            self.assertTrue(path.is_file(), f'not a file: {path}')

    def test_scripts_are_executable(self):
        """All scripts are user+group executable."""
        for name in ('sprint.sh', 'scan.sh', 'generate.sh', 'diff.sh', 'status.sh', 'install-skill.sh'):
            path = SCRIPTS_DIR / name
            mode = path.stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR, f'not executable: {path}')
            self.assertTrue(mode & stat.S_IXGRP, f'not executable (group): {path}')

    def test_scripts_have_shebang(self):
        """All scripts start with #!."""
        for name in ('sprint.sh', 'scan.sh', 'generate.sh', 'diff.sh', 'status.sh', 'install-skill.sh'):
            path = SCRIPTS_DIR / name
            first = path.read_text(encoding='utf-8').splitlines()[:1]
            self.assertTrue(first, f'{path} is empty')
            self.assertTrue(first[0].startswith('#!'), f'{path} has no shebang: {first[0]!r}')

    def test_scripts_have_purpose_comment(self):
        """All scripts have a Purpose: line in the header."""
        for name in ('sprint.sh', 'scan.sh', 'generate.sh', 'diff.sh', 'status.sh', 'install-skill.sh'):
            path = SCRIPTS_DIR / name
            head = '\n'.join(path.read_text(encoding='utf-8').splitlines()[:5])
            self.assertIn('Purpose:', head, f'{path} missing Purpose comment in header')

    def test_scripts_pass_bash_syntax(self):
        """All scripts pass bash -n."""
        bash = shutil.which('bash')
        if not bash:
            self.skipTest('bash not on PATH')
        for name in ('sprint.sh', 'scan.sh', 'generate.sh', 'diff.sh', 'status.sh', 'install-skill.sh'):
            path = SCRIPTS_DIR / name
            result = subprocess.run([bash, '-n', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f'{path} failed bash -n:\n{result.stderr}')

class TestTemplates(unittest.TestCase):

    def test_draft_template_exists(self):
        """templates/draft_template.md exists."""
        self.assertTrue((TEMPLATES_DIR / 'draft_template.md').exists())

    def test_draft_template_has_placeholders(self):
        """Draft template has the documented placeholders."""
        text = (TEMPLATES_DIR / 'draft_template.md').read_text()
        for ph in ('{FILENAME}', '{PURPOSE}', '{IMPORTS}', '{PUBLIC_FUNCS}', '{CONSTANTS}'):
            self.assertIn(ph, text, f'draft_template missing placeholder: {ph}')

    def test_inline_template_exists(self):
        """templates/inline_template.md exists."""
        self.assertTrue((TEMPLATES_DIR / 'inline_template.md').exists())

    def test_sprint_checklist_exists(self):
        """templates/sprint_checklist.md exists."""
        self.assertTrue((TEMPLATES_DIR / 'sprint_checklist.md').exists())

class TestSmokeRun(unittest.TestCase):
    """End-to-end smoke tests against a tiny synthesized repo."""

    def setUp(self):
        """Set up a tiny repo with one .py file."""
        self.tmp = tempfile.mkdtemp(prefix='sprint-smoke-')
        (Path(self.tmp) / 'main.py').write_text('def foo(): pass\n', encoding='utf-8')

    def tearDown(self):
        """Remove the temp repo."""
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan_sh_runs(self):
        """scan.sh exits 0 on a small repo."""
        proc = subprocess.run(['bash', str(SCRIPTS_DIR / 'scan.sh'), self.tmp], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('Source files scanned', proc.stdout)
        self.assertIn('1', proc.stdout)

    def test_diff_sh_runs(self):
        """diff.sh exits 0 on a small repo."""
        proc = subprocess.run(['bash', str(SCRIPTS_DIR / 'diff.sh'), self.tmp], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('main.py', proc.stdout)

    def test_status_sh_runs(self):
        """status.sh exits 0 or 1 on a small repo."""
        proc = subprocess.run(['bash', str(SCRIPTS_DIR / 'status.sh'), self.tmp], capture_output=True, text=True, timeout=30)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)

    def test_generate_sh_creates_doc(self):
        """generate.sh creates the .doc.md file."""
        proc = subprocess.run(['bash', str(SCRIPTS_DIR / 'generate.sh'), str(Path(self.tmp) / 'main.py')], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((Path(self.tmp) / 'main.doc.md').exists(), 'generate.sh did not create main.doc.md')

    def test_sprint_sh_dry_run(self):
        """sprint.sh --dry-run --auto runs end-to-end."""
        proc = subprocess.run(['bash', str(SCRIPTS_DIR / 'sprint.sh'), self.tmp, '--dry-run', '--auto', '--no-scan-update'], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, f'sprint --dry-run failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}')
        self.assertIn('Sprint complete', proc.stdout)

class TestInstallSkillScript(unittest.TestCase):
    """The install-skill.sh script must work in --dry-run mode."""

    def test_dry_run(self):
        """install-skill.sh --dry-run exits 0."""
        proc = subprocess.run(['bash', str(SCRIPTS_DIR / 'install-skill.sh'), '--dry-run', '--skip-smoke'], capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('DRY-RUN', proc.stdout)
        self.assertIn('Install complete', proc.stdout)
if __name__ == '__main__':
    unittest.main()
