"""Profiles (DESIGN §3): everything MO stores belongs to exactly one profile.

    ~/.mo/profiles/<name>/
        profile.json   name, created
        seeds/         one file per seed (step 2)
        tunes/         one file per sealed tune box (step 3)

Only the HUMAN USER creates or deletes profiles, through the MO box. Deleting is permanent.
"""

from __future__ import annotations

import json
import re
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
    """Permanent. Returns what was deleted."""
    if not exists(name):
        raise ValueError(f"No profile named {normalize(name)!r}")
    lost = summary(name)
    shutil.rmtree(_dir(name))
    return lost
