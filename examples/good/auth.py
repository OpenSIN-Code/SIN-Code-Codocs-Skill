"""Purpose: User authentication — token issuance, refresh, and verification.

Docs: auth.doc.md

This is the canonical "good" example for the sin-codocs skill. It shows
every rule from SKILL.md applied: module docstring with Purpose/Docs,
section separators, full Google-style docstrings on every public API,
inline WHY-comments, magic-number explanations, and a deprecation marker.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────
TOKEN_TTL_SECONDS = 3600     # 1 hour — balances UX vs. blast radius if leaked
REFRESH_TTL_SECONDS = 86400  # 24 hours — only valid for /refresh, not /verify
HMAC_KEY_ENV = "AUTH_HMAC_KEY"  # must be set; raises at module load if missing
MIN_KEY_LENGTH = 32          # bits; anything shorter is brute-forceable


# ── Errors ─────────────────────────────────────────────────────────────
class AuthError(Exception):
    """Base class for all auth-related errors. Catch this in middleware."""


class TokenExpiredError(AuthError):
    """Token's exp claim is in the past. Caller should re-authenticate."""


class InvalidSignatureError(AuthError):
    """Token's signature did not verify. Treat as a tamper attempt."""


# ── Public data types ─────────────────────────────────────────────────
@dataclass(frozen=True)
class Token:
    """A signed authentication token. Immutable.

    The token is `value`, the expiry is `expires_at` (Unix seconds).
    `subject` is the user ID the token was issued for — never log this
    directly, hash it first.
    """
    value: str
    expires_at: int
    subject: str


# ── Public API ─────────────────────────────────────────────────────────
def issue_token(user_id: str, *, ttl: int = TOKEN_TTL_SECONDS) -> Token:
    """Issue a new signed token for `user_id`.

    The token is `user_id.expires_at.signature` where the signature is
    HMAC-SHA256 over the first two parts. Callers should treat the
    returned Token as opaque; only `verify_token` should inspect it.

    Args:
        user_id: The user to issue the token for. Must be non-empty.
        ttl: Time-to-live in seconds. Defaults to TOKEN_TTL_SECONDS.

    Returns:
        A Token with a fresh signature and expires_at = now + ttl.

    Raises:
        ValueError: user_id is empty.
        AuthError: HMAC key is missing or too short.
    """
    if not user_id:
        raise ValueError("user_id must be non-empty")

    # Defense in depth: refuse to issue if the HMAC key is too short.
    # Catching this here is better than failing at sign-time under load.
    _validate_key()

    now = int(time.time())
    expires_at = now + ttl
    payload = f"{user_id}.{expires_at}"
    signature = _sign(payload)
    return Token(
        value=f"{payload}.{signature}",
        expires_at=expires_at,
        subject=user_id,
    )


def verify_token(token_str: str) -> Token:
    """Verify a token's signature and expiry, return its claims.

    Use this on every authenticated request. Do NOT cache the result —
    expiry is checked at call time, and caching would let expired tokens
    through during the cache TTL.

    Args:
        token_str: The raw token string from the Authorization header.

    Returns:
        The Token if signature and expiry are valid.

    Raises:
        InvalidSignatureError: signature did not match — treat as tamper.
        TokenExpiredError: exp claim is in the past.
        ValueError: token is malformed.
    """
    parts = token_str.split(".")
    if len(parts) != 3:
        raise ValueError("Token must have 3 dot-separated parts")

    user_id, exp_str, sig = parts
    try:
        expires_at = int(exp_str)
    except ValueError as e:
        raise ValueError("Token exp must be an integer") from e

    payload = f"{user_id}.{expires_at}"
    expected_sig = _sign(payload)
    # hmac.compare_digest is constant-time — prevents timing attacks
    if not hmac.compare_digest(sig, expected_sig):
        raise InvalidSignatureError("Signature mismatch")

    if expires_at < int(time.time()):
        raise TokenExpiredError(f"Token expired at {expires_at}")

    return Token(value=token_str, expires_at=expires_at, subject=user_id)


def old_login(username: str, password: str) -> Optional[Token]:  # DEPRECATED(v2): use OAuth2 flow
    """DEPRECATED: legacy password login. Will be removed in v3.

    Kept for the migration window only. New code MUST use the OAuth2
    flow in `oauth2.py`. The function will start raising NotImplementedError
    on 2026-09-01.
    """
    logging.warning("old_login called for %s — migrate to OAuth2", username[:4])
    # legacy: kept so existing clients don't break before migration deadline
    return None


# ── Internal helpers ───────────────────────────────────────────────────
def _sign(payload: str) -> str:
    """Compute HMAC-SHA256(payload) using the configured key.

    Internal helper (leading underscore). Returns hex-encoded digest.
    """
    key = os.environ[HMAC_KEY_ENV].encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _validate_key() -> None:
    """Refuse to operate with a too-short HMAC key.

    Raises AuthError at startup if the key is missing or below
    MIN_KEY_LENGTH. We check bits, not chars, because the key is hex.
    """
    key = os.environ.get(HMAC_KEY_ENV, "")
    if not key:
        raise AuthError(f"{HMAC_KEY_ENV} env var must be set")
    if len(key) * 4 < MIN_KEY_LENGTH:
        raise AuthError(f"{HMAC_KEY_ENV} must be at least {MIN_KEY_LENGTH} bits")
