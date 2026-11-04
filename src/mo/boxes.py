"""MO boxes and their keys (DESIGN §8).

Each box gets a one-time secret key. MO hands it to the box in the tool result's hidden `_meta`
(the box can read it; ChatGPT can't), and only calls signed with it count as the HUMAN USER.
MO stores a hash of the key, never the key itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Any

from mo.events import current_user, data_root, mo_home

_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _path(box_id: str):
    if not _ID_RE.match(box_id):
        raise ValueError(f"Unknown box {box_id!r}")
    return mo_home() / "boxes" / f"{box_id}.json"


def open_box(kind: str, **data: Any) -> tuple[dict[str, Any], str]:
    """Create a box. Returns the box and its key; the key goes only into hidden `_meta`."""
    box_id, key = secrets.token_hex(4), secrets.token_urlsafe(24)
    while (data_root() / "box-owners" / box_id).exists():  # ids are shared across users: never reuse one
        box_id = secrets.token_hex(4)
    box = {"id": box_id, "kind": kind, "opened": time.time(), "key_hash": _hash(key), **data}
    path = _path(box_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(box))
    # Routing only: which user this window belongs to, so its direct-line calls act for that user.
    owners = data_root() / "box-owners"
    owners.mkdir(parents=True, exist_ok=True)
    (owners / box_id).write_text(current_user() or "")
    return box, key


def owner(box_id: str) -> str | None:
    """The user a window was opened for (from that call's sign-in token), or None."""
    if not _ID_RE.match(box_id):
        return None
    path = data_root() / "box-owners" / box_id
    user = path.read_text().strip() if path.exists() else ""
    return user or None


def save(box: dict[str, Any]) -> None:
    _path(box["id"]).write_text(json.dumps(box))


def load(box_id: str) -> dict[str, Any] | None:
    try:
        path = _path(box_id)
    except ValueError:
        return None
    return json.loads(path.read_text()) if path.exists() else None


def verify(box_id: str, key: str) -> dict[str, Any] | None:
    """The box, if `key` is that box's key; otherwise None."""
    box = load(box_id)
    if box is None or not isinstance(key, str):
        return None
    return box if hmac.compare_digest(box["key_hash"], _hash(key)) else None
