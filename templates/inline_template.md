<!--
  Template: inline_template.md
  Purpose: Show the inline-comment work the human must do after a sprint
  Docs: ../SKILL.md (Inline fill-in work)

  The sprint tool ONLY generates .doc.md companions. It does NOT
  modify the source file's inline comments. After the sprint, a
  human should run through this checklist for every file that got a
  new .doc.md.

  All of these patterns come from the sin-codocs skill — see
  ~/.config/opencode/skills/sin-codocs/templates/inline-header.md
  for the canonical version.
-->

# ── 1. Add the file-level Purpose/Docs header (Python) ─────────────
"""Purpose: <one-line description>

Docs: <this-file>.doc.md

<optional longer description — 1-2 sentences.>
"""


# ── 2. Add the file-level header (non-Python) ──────────────────────
// Purpose: <one-line description>
// Docs: <this-file>.doc.md


# ── 3. Section separators (every 30-50 lines) ─────────────────────
// ── Public API ───────────────────────────────────────────────────


# ── 4. Magic values with WHY comments ────────────────────────────
MAX_RETRIES = 3        # upstream SLA guarantees < 2 failures per 1000
WAIT_SECONDS = 60      # must match upstream rate-limit window
TIMEOUT_MS = 50        # MUST be < retry-after of upstream (60ms)


# ── 5. Public function docstrings (Google style) ──────────────────
def public_function(arg: str) -> str:
    """Short one-line description.

    Longer WHY-explanation. Args / Returns / Raises sections.
    Explain the *why* of each branch, not the *what* (visible from
    the code).

    Args:
        arg: What this argument is, what valid values it accepts.

    Returns:
        What the caller gets back.

    Raises:
        ValueError: When and why this is raised.
    """
    ...


# ── 6. Non-obvious logic: WHY comment ─────────────────────────────
result = compute_thing(x, y)  # not using x*y because float precision loss


# ── 7. Performance note (only when non-obvious) ──────────────────
for user in users:           # O(n²) but n ≤ 10 in practice
    for role in user.roles:
        ...


# ── 8. Security note (always!) ───────────────────────────────────
db.execute(query, params)    # parameterized — prevents SQL injection here


# ── 9. Deprecation marker ────────────────────────────────────────
def old_login():  # DEPRECATED(v2): use authenticate() instead
    ...


# ── 10. Edge case handler ────────────────────────────────────────
if value is None:            # protocol allows null in this field
    return default
