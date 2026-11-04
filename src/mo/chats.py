"""Voice per chat (AGENTS.md item 7): each chat's current profile.

A chat is identified by `openai/session`, which ChatGPT's app (not the model) attaches to every
tool call. Only the HUMAN USER sets a chat's voice, from an MO box in that chat. Nothing is
inherited: a chat without a voice asks.

    ~/.mo/chats/<hash of chat id>.json   {"profile": …, "set": …}
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from mo import profiles
from mo.events import mo_home


def _path(chat: str) -> Path:
    return mo_home() / "chats" / f"{hashlib.sha256(chat.encode()).hexdigest()[:24]}.json"


def voice(chat: str | None) -> str | None:
    """The chat's voice, or None if it has none (or its profile was deleted, or there's no chat id)."""
    if not chat:
        return None
    path = _path(chat)
    name = json.loads(path.read_text())["profile"] if path.exists() else None
    return name if name and profiles.exists(name) else None


def set_voice(chat: Any, name: Any) -> str:
    if not isinstance(chat, str) or not chat:
        raise ValueError("This box doesn't know its chat, so it can't set a voice. Open a new MO box.")
    name = profiles.normalize(name)
    if not profiles.exists(name):
        raise ValueError(f"No profile named {name!r}")
    path = _path(chat)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"profile": name, "set": time.time()}))
    return name


def forget_profile(name: str) -> int:
    """After a profile is deleted, the chats that used it have no voice (they ask again)."""
    folder = mo_home() / "chats"
    cleared = 0
    for path in folder.glob("*.json") if folder.is_dir() else []:
        if json.loads(path.read_text()).get("profile") == name:
            path.unlink()
            cleared += 1
    return cleared


def _latest_path(chat: str) -> Path:
    return mo_home() / "chats" / f"{hashlib.sha256(chat.encode()).hexdigest()[:24]}.latest"


def set_latest(chat: str, box_id: str) -> None:
    """The chat's newest MO window. Older windows in the chat become read-only."""
    path = _latest_path(chat)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(box_id)


def latest(chat: str | None) -> str | None:
    if not chat:
        return None
    path = _latest_path(chat)
    return path.read_text().strip() if path.exists() else None
