"""Profiles (DESIGN §3): everything MO stores belongs to exactly one profile.

    ~/.mo/profiles/<name>/
        profile.json   name, created
        seeds/         one file per seed, plain text, exactly as given
        tunes/         one file per sealed tune box (step 3)
        runs/          one file per output run

Only the HUMAN USER creates, deletes, or picks profiles, through an MO box. Deleting is permanent.
Which profile a chat uses (its voice) is kept in `mo.chats`.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from mo.events import mo_home

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def normalize(name: Any) -> str:
    """Lowercased, trimmed name; raises ValueError for anything else."""
    if not isinstance(name, str) or not _NAME_RE.match(name.strip().lower()):
        raise ValueError("Use lowercase letters, numbers, and dashes (up to 40), starting with a letter or number")
    return name.strip().lower()


def _root() -> Path:
    return mo_home() / "profiles"


def _dir(name: str) -> Path:
    return _root() / normalize(name)


def exists(name: str) -> bool:
    return (_dir(name) / "profile.json").exists()


def create(name: str) -> dict[str, Any]:
    name = normalize(name)
    if exists(name):
        raise ValueError(f"A profile named {name!r} already exists")
    folder = _dir(name)
    for sub in ("seeds", "tunes"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    profile = {"name": name, "created": time.time()}
    (folder / "profile.json").write_text(json.dumps(profile))
    return summary(name)


def summary(name: str) -> dict[str, Any]:
    folder = _dir(name)
    profile = json.loads((folder / "profile.json").read_text())
    count = lambda sub: sum(1 for p in (folder / sub).glob("*.json"))  # noqa: E731
    return {"name": profile["name"], "created": profile["created"], "seeds": count("seeds"), "tunes": count("tunes")}


def list_all() -> list[dict[str, Any]]:
    root = _root()
    names = sorted(p.parent.name for p in root.glob("*/profile.json")) if root.is_dir() else []
    return [summary(n) for n in names]


def delete(name: str) -> dict[str, Any]:
    """Permanent. Returns what was deleted (its runs go with it)."""
    if not exists(name):
        raise ValueError(f"No profile named {normalize(name)!r}")
    lost = summary(name)
    shutil.rmtree(_dir(name))
    return lost


def plain_text(text: Any) -> str:
    """What MO stores for a seed: plain text with unified line breaks, nothing else changed."""
    if not isinstance(text, str):
        raise ValueError("Paste some text")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("Paste some text")
    return text


def add_seed(name: str, text: str, box: str) -> dict[str, Any]:
    if not exists(name):
        raise ValueError(f"Profile {normalize(name)!r} no longer exists; pick another")
    seed = {"id": secrets.token_hex(4), "added": time.time(), "box": box,
            "words": len(text.split()), "text": text}
    (_dir(name) / "seeds" / f"{seed['id']}.json").write_text(json.dumps(seed, ensure_ascii=False))
    return seed


def seeds(name: str) -> list[dict[str, Any]]:
    """Every seed in a profile, oldest first, with its full text."""
    if not exists(name):
        raise ValueError(f"No profile named {normalize(name)!r}")
    found = [json.loads(p.read_text()) for p in (_dir(name) / "seeds").glob("*.json")]
    return sorted(found, key=lambda s: s["added"])


def delete_seeds(name: str, ids: Any) -> list[str]:
    """Permanent. Deletes the given seeds; returns the ids actually deleted."""
    if not exists(name):
        raise ValueError(f"Profile {normalize(name)!r} no longer exists; pick another")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError("Pick the seeds to delete")
    deleted = []
    for seed_id in ids:
        path = _dir(name) / "seeds" / f"{seed_id}.json"
        if re.fullmatch(r"[0-9a-f]{8}", seed_id) and path.exists():
            path.unlink()
            deleted.append(seed_id)
    return deleted


def clear_seeds(name: str) -> int:
    """Permanent. Removes every seed; tunes stay. Returns how many were removed."""
    if not exists(name):
        raise ValueError(f"No profile named {normalize(name)!r}")
    files = list((_dir(name) / "seeds").glob("*.json"))
    for f in files:
        f.unlink()
    return len(files)
