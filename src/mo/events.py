"""The append-only event log: MO's source of truth and its observability (DESIGN §9).

Every event names exactly one actor (DESIGN §2):

    HUMAN USER  a call over an MO box's direct line, signed with that box's key
    CHATGPT     an ordinary tool call
    MO          MO's own code (including refusals)
    DEV         a dev-only endpoint on this computer
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

HUMAN_USER, CHATGPT, MO, DEV = "HUMAN USER", "CHATGPT", "MO", "DEV"
ACTORS = (HUMAN_USER, CHATGPT, MO, DEV)


class NoUser(RuntimeError):
    """MO was asked for user data with no user to scope it to. Never falls back to shared storage."""


_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_user: contextvars.ContextVar[str | None] = contextvars.ContextVar("mo_user", default=None)


def data_root() -> Path:
    """MO's whole store: /data when hosted (HOSTING.md §3)."""
    return Path(os.environ.get("MO_HOME", Path.home() / ".mo"))


def current_user() -> str | None:
    """The user this request acts for: set explicitly (a window's owner), or the sign-in token's
    subject on a ChatGPT tool call. Never anything ChatGPT says."""
    from mcp.server.auth.middleware.auth_context import get_access_token
    token = get_access_token()
    if token is not None:  # a signed-in call: the token decides, nothing else
        return token.subject or None
    return _user.get()


@contextmanager
def as_user(user: str) -> Iterator[None]:
    """Act for `user` (e.g. the owner of the window that sent a click)."""
    reset = _user.set(user)
    try:
        yield
    finally:
        _user.reset(reset)


def mo_home() -> Path:
    """The current user's folder: data → users → <user id>. No user → NoUser, never a default."""
    user = current_user()
    if not user or not _USER_ID.match(user):
        raise NoUser("no signed-in user for this request")
    return data_root() / "users" / user


def _path() -> Path:
    try:
        return mo_home() / "events.jsonl"
    except NoUser:
        return data_root() / "mo-events.jsonl"  # MO-wide events with no user (e.g. refusals); no text


def record(actor: str, type: str, **data: Any) -> dict[str, Any]:
    if actor not in ACTORS:
        raise ValueError(f"Unknown actor {actor!r}")
    event = {"at": time.time(), "actor": actor, "type": type, **data}
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read(**filters: Any) -> list[dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [e for e in events if all(e.get(k) == v for k, v in filters.items() if v is not None)]


def purge_profile(name: str) -> int:
    """Remove every event that belongs to a profile (deleting a profile is permanent, its trace
    included). Returns how many were removed. The caller records the tombstone afterwards."""
    path = _path()
    if not path.exists():
        return 0
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    kept = [line for line in lines if json.loads(line).get("profile") != name]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(line + "\n" for line in kept))
    tmp.replace(path)
    return len(lines) - len(kept)
