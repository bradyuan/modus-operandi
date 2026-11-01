"""The append-only event log: MO's source of truth and its observability (DESIGN §9).

Every event names exactly one actor (DESIGN §2):

    HUMAN USER  a call over an MO box's direct line, signed with that box's key
    CHATGPT     an ordinary tool call
    MO          MO's own code (including refusals)
    DEV         a dev-only endpoint on this computer
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

HUMAN_USER, CHATGPT, MO, DEV = "HUMAN USER", "CHATGPT", "MO", "DEV"
ACTORS = (HUMAN_USER, CHATGPT, MO, DEV)


def mo_home() -> Path:
    return Path(os.environ.get("MO_HOME", Path.home() / ".mo"))


def _path() -> Path:
    return mo_home() / "events.jsonl"


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
