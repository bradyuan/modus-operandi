"""Sign-in (HOSTING.md §2): ChatGPT's "Connect" signs the user in with WorkOS AuthKit; every call
carries an access token. MO checks the token's signature against AuthKit's public keys, its issuer
and its expiry, and takes the user from it. ChatGPT never says who the user is.

Admins: a user whose *verified* email (looked up at WorkOS, not stored) is in `MO_ADMINS`.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

AUTHKIT = os.environ.get("MO_AUTHKIT", "https://nurturing-airplane-88-staging.authkit.app").rstrip("/")
WORKOS_API = "https://api.workos.com"


class AuthKitVerifier(TokenVerifier):
    """A token counts only if AuthKit signed it, it was issued by this AuthKit, and it hasn't expired."""

    def __init__(self, issuer: str = AUTHKIT) -> None:
        self.issuer = issuer
        self._keys = jwt.PyJWKClient(f"{issuer}/oauth2/jwks", cache_keys=True)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            key = self._keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=["RS256"], issuer=self.issuer,
                                options={"require": ["sub", "iss", "exp"], "verify_aud": False})
        except (jwt.PyJWTError, jwt.PyJWKClientError):
            return None
        return AccessToken(token=token, client_id=str(claims.get("client_id") or claims.get("azp") or ""),
                           scopes=str(claims.get("scope", "")).split(), expires_at=claims.get("exp"),
                           subject=claims["sub"], claims=claims)


_admin_cache: dict[str, tuple[bool, float]] = {}


def is_admin(user_id: str) -> bool:
    """True only if WorkOS says this user's email is verified and it's in MO_ADMINS."""
    admins = {e.strip().lower() for e in os.environ.get("MO_ADMINS", "").split(",") if e.strip()}
    api_key = os.environ.get("WORKOS_API_KEY")
    if not admins or not api_key:
        return False
    hit = _admin_cache.get(user_id)
    if hit and time.time() - hit[1] < 600:
        return hit[0]
    try:
        r = httpx.get(f"{WORKOS_API}/user_management/users/{user_id}",
                      headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        user: dict[str, Any] = r.json() if r.status_code == 200 else {}
    except httpx.HTTPError:
        return False  # can't check → not admin (never assume)
    result = bool(user.get("email_verified")) and str(user.get("email", "")).lower() in admins
    _admin_cache[user_id] = (result, time.time())
    return result
