<!--
  Template: inline-header.md
  Purpose: Show the exact form a SOTA inline header block takes
  Docs: ../SKILL.md (Layer 2 — SOTA Inline Documentation)

  Use this as a copy-paste reference when you need to add a header to
  a non-Python file (TS, Go, Rust, …). For Python, use the
  `templates/module.py.template` triple-quoted docstring instead.
-->

# ── File header (every code file) ────────────────────────────────────
# Purpose: <what this file does in 1 line>
# Docs: <this-file>.doc.md


# ── Section separator (every 30-50 lines) ───────────────────────────
# Use a single long line of box-drawing dashes. Make the section name
# the same length on both sides for visual symmetry.
# ── Auth ────────────────────────────────────────────────────────────


# ── Magic value with explanation ────────────────────────────────────
MAX_RETRIES = 3    # upstream SLA guarantees < 2 failures per 1000
WAIT_SECONDS = 60  # must match upstream rate-limit window
TIMEOUT_MS = 50    # MUST be < retry-after of upstream (60ms)


# ── Non-obvious logic: WHY comment ──────────────────────────────────
result = compute_thing(x, y)  # not using x*y because precision loss in float


# ── Performance note ────────────────────────────────────────────────
for user in users:           # O(n²) but n ≤ 10 in practice
    for role in user.roles:
        ...


# ── Security note ───────────────────────────────────────────────────
db.execute(query, params)    # parameterized — prevents SQL injection


# ── Edge case handler ───────────────────────────────────────────────
if value is None:            # protocol allows null in this field
    return default


# ── Deprecation marker ──────────────────────────────────────────────
def old_login():  # DEPRECATED(v2): use authenticate() instead
    ...


# ── TODO with context ───────────────────────────────────────────────
def parse_response(r):  # TODO(2026-Q3): switch to streaming parser
    return r.json()
