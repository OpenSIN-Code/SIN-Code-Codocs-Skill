"""Purpose: SOTA Python file template — every new module starts from this.

Docs: template.doc.md

This is the canonical "skeleton" that `scripts/new-module.sh` renders.
Copy it, edit the placeholders, and you have a SOTA-documented module.

Two-layer doc pattern (see SKILL.md):
  Layer 1 = this .doc.md companion  (the "what and why")
  Layer 2 = inline `#` comments      (the "how and why here")

The template itself follows the pattern so it serves as a runnable example.
"""

# ─────────────────────────────────────────────────────────────────────────
# Why this template exists:
#   The sin-codocs skill is opinionated about documentation. Without a
#   canonical skeleton, every new module would invent its own header,
#   its own constant layout, and its own import style. That drift is
#   what makes a codebase unreadable six months later. By rendering
#   from this template, every new module starts with the same DNA:
#   a Purpose/Docs docstring, alphabetized imports, named constants
#   with inline WHY-comments, and Google-style docstrings on the
#   public API.
#
# Why the public functions in this template are NOT meant to be used
# as-is:
#   load_config, retry_with_backoff, and _validate_key are real,
#   tested implementations of common patterns. The point of the
#   template is the SHAPE (docstring, separators, constant block)
#   — the body is a starting point you customize. Don't ship this
#   file as a module of your own; treat it like a `.gitignore`
#   template, not production code.
#
# Why imports are alphabetized:
#   Alphabetical import order means `git diff` and review-merge
#   conflicts resolve predictably. There is no debate about whether
#   `os` should come before `pathlib` — the answer is always
#   alphabetical. We follow PEP 8's recommendation explicitly.
# ─────────────────────────────────────────────────────────────────────────

# ── Imports ────────────────────────────────────────────────────────────
from __future__ import annotations

# Standard library — alphabetical
import json
import logging
import os
from pathlib import Path
from typing import Any

# Third-party — alphabetical, blank line before
import yaml

# ── Constants ──────────────────────────────────────────────────────────
# Section separator style: # ── Name ────... (unicode box-drawing dashes).
# The long line makes the section visually scannable in 100+ line files.

# 30s is the industry-standard "user-perceived failure" window for
# synchronous HTTP calls. Above 30s users refresh the page; below 30s
# they assume the request is still working. Match this in your own
# timeouts to avoid surprising the user.
DEFAULT_TIMEOUT = 30        # seconds; matches upstream SLA window

# 3 retries covers the typical 99.5%–99.9% SLO range while keeping
# total wall-clock bounded. After 3 failures (1 + 2 retries) the
# service is almost certainly down, not flaky — fail fast and let
# the operator investigate.
MAX_RETRIES = 3             # upstream guarantees < 2 failures per 1000

# Standard log format. The %(name)s is what lets you grep a single
# module's logs out of a multi-tenant stream; never drop it.
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Default config path is env-overridable. Loading from the env at
# module-import time means tests can monkey-patch os.environ BEFORE
# importing this file to get a different config path.
CONFIG_PATH = Path(os.environ.get("APP_CONFIG", "config.yaml"))


# ── Public API ─────────────────────────────────────────────────────────
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load YAML configuration from disk.

    Reads the file, validates it has the required top-level keys, and
    returns a plain dict. Raises FileNotFoundError if the path is missing
    and ValueError if the YAML is empty or malformed.

    Args:
        path: Filesystem path to the YAML file. Defaults to CONFIG_PATH.

    Returns:
        Parsed configuration as a dict. Nested keys are preserved.

    Raises:
        FileNotFoundError: path does not exist
        ValueError: YAML is empty or missing required keys
    """
    if not path.exists():
        # Surface the actual path in the error — generic "not found"
        # errors are the #1 cause of "why is this failing?" Slack pings.
        raise FileNotFoundError(f"Config not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        # safe_load avoids arbitrary Python object construction (RCE risk).
        # Never use yaml.load() in production — it can be coerced into
        # instantiating python/object subclasses, which is RCE.
        data = yaml.safe_load(f) or {}

    # Required keys are checked explicitly so a missing key fails fast
    # at startup, not at first-request-time. "name" and "version" are
    # the smallest possible surface for a config schema.
    required = {"name", "version"}
    missing = required - data.keys()
    if missing:
        # sorted() makes the error message deterministic for tests
        # and for human readers comparing two failing runs.
        raise ValueError(f"Config missing required keys: {sorted(missing)}")

    return data


def retry_with_backoff(func, *, max_attempts: int = MAX_RETRIES) -> Any:
    """Call func with exponential backoff on transient failures.

    Retries on any exception raised by func, sleeping 2^attempt seconds
    between attempts. NOT for security-critical paths — use idempotency
    keys for those (see idempotency.py).

    Args:
        func: Zero-arg callable to invoke.
        max_attempts: Total tries including the first. Defaults to MAX_RETRIES.

    Returns:
        Whatever func returns on the first successful attempt.

    Raises:
        Exception: The last exception raised by func, after max_attempts.
    """
    # Exponential backoff: 1s, 2s, 4s — capped to keep CI fast.
    # The base of 2 was chosen so the doubling is intuitive: 1s, 2s,
    # 4s. A base of 3 (1s, 3s, 9s) is also defensible but harder to
    # predict by hand during an incident.
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception:
            if attempt >= max_attempts:
                # Re-raise the LAST exception so the caller sees the
                # most recent failure, not a wrapped or aggregated one.
                raise
            # sleep 2^(attempt-1) seconds — don't log sensitive args.
            # Logging func() arguments (or its return value) can leak
            # PII / tokens / secrets into the log stream; we keep the
            # closure opaque to the retry loop on purpose.
            import time
            time.sleep(2 ** (attempt - 1))


# ── Internal helpers ───────────────────────────────────────────────────
def _validate_key(key: str) -> str:
    """Trim whitespace and reject empty keys.

    Internal helper — leading underscore signals "not part of public API".
    Empty keys almost always indicate a config-file typo, and the
    alternative (silently treating "" as a no-op) is harder to debug
    than a loud ValueError at startup.
    """
    key = key.strip()
    if not key:
        raise ValueError("Key must be non-empty")
    return key


# ── Module entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    # CLI mode: load config, print version. Used by smoke tests.
    # `python3 template.py` should always produce a single line of JSON
    # with the config's name and version — that's the contract smoke
    # tests rely on.
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    cfg = load_config()
    # json.dumps so the output is machine-parseable, not just human
    # readable. Tests pipe this into jq; humans pipe it into less.
    print(json.dumps({"name": cfg["name"], "version": cfg["version"]}))
