"""Bearer-token authentication.

Tokens are static for this demo: the token *is* the user id, prefixed with
`tok-`. A real service would look them up.
"""

from __future__ import annotations

from fastapi import Header, HTTPException

TOKEN_PREFIX = "tok-"


def current_user(authorization: str = Header(default="")) -> str:
    """Return the user id for a `Bearer tok-<user>` header."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="missing or invalid token")
    user = token[len(TOKEN_PREFIX):]
    if not user:
        raise HTTPException(status_code=401, detail="empty user")
    return user
