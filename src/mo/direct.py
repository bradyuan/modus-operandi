"""The MO box's direct line: actions only the HUMAN USER can take (DESIGN §8).

Every call here has already been verified as signed with its box's key. ChatGPT has no path to
these actions. Each action returns (HTTP status, reply for the box) and records its event.
"""

from __future__ import annotations

import secrets
from typing import Any

from mo import boxes, events, profiles
from mo.events import HUMAN_USER, MO


def handle(box: dict[str, Any], body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    action = body.get("action")
    handler = ACTIONS.get(box["kind"], {}).get(action)
    if handler is None:
        return refuse(box, action, f"{action!r} isn't an action for a {box['kind']} box")
    try:
        return handler(box, body)
    except ValueError as exc:
        return refuse(box, action, str(exc), status=400)


def refuse(box: dict[str, Any], action: Any, reason: str, status: int = 403) -> tuple[int, dict[str, Any]]:
    events.record(MO, "refused", box=box["id"], action=action, reason=reason)
    return status, {"error": reason}


# --- profiles box

def _list(box, body):
    return 200, {"profiles": profiles.list_all()}


def _create(box, body):
    created = profiles.create(body.get("name"))
    events.record(HUMAN_USER, "profile_created", box=box["id"], profile=created["name"])
    return 200, {"created": created, "profiles": profiles.list_all()}


def _delete(box, body):
    """Step 1 of 2: say what will be lost and issue a one-time confirmation code."""
    name = profiles.normalize(body.get("name"))
    if not profiles.exists(name):
        raise ValueError(f"No profile named {name!r}")
    box["pending_delete"] = {"profile": name, "code": secrets.token_urlsafe(12)}
    boxes.save(box)
    events.record(HUMAN_USER, "profile_delete_requested", box=box["id"], profile=name)
    return 200, {"confirm": box["pending_delete"]["code"], "will_lose": profiles.summary(name)}


def _confirm_delete(box, body):
    """Step 2 of 2: delete permanently, only with the code from step 1 for the same profile."""
    pending = box.pop("pending_delete", None)
    boxes.save(box)
    name = profiles.normalize(body.get("name"))
    if not pending or pending["profile"] != name or not secrets.compare_digest(pending["code"], str(body.get("confirm"))):
        raise ValueError("Delete wasn't confirmed; click Delete again")
    lost = profiles.delete(name)
    purged = events.purge_profile(name)
    # The tombstone names the profile in `deleted_profile`, not `profile`, so it stays in "All" and
    # never shows up under a new profile that reuses the name.
    events.record(HUMAN_USER, "profile_deleted", box=box["id"], deleted_profile=name,
                  lost={"seeds": lost["seeds"], "tunes": lost["tunes"], "events": purged})
    return 200, {"deleted": lost, "profiles": profiles.list_all()}


ACTIONS = {
    "profiles": {"list": _list, "create": _create, "delete": _delete, "confirm_delete": _confirm_delete},
}
