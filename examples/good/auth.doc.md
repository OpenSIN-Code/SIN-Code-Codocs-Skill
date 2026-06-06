# auth.py

**Purpose:** User authentication — token issuance, refresh, and verification.

**Docs:** auth.doc.md (this file)

## What it does

Provides token-based authentication utilities including HMAC-SHA256 signed
tokens, expiry verification, and deprecation markers for legacy password login.

## Dependencies

- **hashlib, hmac, os, time** — standard library for crypto and timing
- **dataclasses, typing** — data structures and type hints

## Usage examples

```python
from auth import issue_token, verify_token, Token

# Set the required env var before use
import os
os.environ["AUTH_HMAC_KEY"] = "a-very-secret-key-that-is-32-bits-long-or-more"

token = issue_token("user-123")
verified = verify_token(token.value)
```

## Known caveats

- `HMAC_KEY_ENV` must be set at module load time or `_validate_key()` raises.
- `old_login()` is deprecated and will be removed on 2026-09-01.
