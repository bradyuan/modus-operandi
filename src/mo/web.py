"""The trace page's sign-in (HOSTING.md §4): the same WorkOS account as in ChatGPT, in the browser.

/trace/login → WorkOS (Google / Microsoft) → /trace/callback?code=… → MO trades the code for the user
at WorkOS (server to server, with the API key) → a signed session cookie, valid 7 days. The cookie
holds only the user ID and its expiry, signed with MO_SESSION_SECRET, so it can't be forged or edited.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import urlencode

import httpx

from mo.auth import WORKOS_API

COOKIE, STATE_COOKIE = "mo_session", "mo_signin_state"
SESSION_DAYS = 7


def _secret() -> bytes:
    secret = os.environ.get("MO_SESSION_SECRET")
    if not secret:
        raise RuntimeError("MO_SESSION_SECRET isn't set; the trace can't sign anyone in")
    return secret.encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_session(user: str, now: float | None = None) -> str:
    expires = int((now or time.time()) + SESSION_DAYS * 86400)
    payload = base64.urlsafe_b64encode(f"{user}|{expires}".encode()).decode()
    return f"{payload}.{_sign(payload)}"


def session_user(cookie: str | None, now: float | None = None) -> str | None:
    """The signed-in user, if the cookie is MO's own, untouched, and not expired."""
    if not cookie or "." not in cookie:
        return None
    payload, signature = cookie.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        user, expires = base64.urlsafe_b64decode(payload.encode()).decode().rsplit("|", 1)
        return user if int(expires) > (now or time.time()) else None
    except (ValueError, UnicodeDecodeError):
        return None


def login_url(redirect_uri: str) -> tuple[str, str]:
    """Where to send the browser to sign in, and the one-time state that must come back with it."""
    state = secrets.token_urlsafe(16)
    query = urlencode({"client_id": os.environ.get("WORKOS_CLIENT_ID", ""), "redirect_uri": redirect_uri,
                       "response_type": "code", "provider": "authkit", "state": state})
    return f"{WORKOS_API}/user_management/authorize?{query}", state


def user_from_code(code: str) -> str | None:
    """Trade WorkOS's one-time code for the user ID (server to server). None if WorkOS says no."""
    try:
        r = httpx.post(f"{WORKOS_API}/user_management/authenticate", timeout=10, json={
            "client_id": os.environ.get("WORKOS_CLIENT_ID", ""),
            "client_secret": os.environ.get("WORKOS_API_KEY", ""),
            "grant_type": "authorization_code", "code": code})
    except httpx.HTTPError:
        return None
    user = r.json().get("user", {}) if r.status_code == 200 else {}
    return user.get("id") or None
