"""The MO box's direct line: actions only the HUMAN USER can take (DESIGN §8).

Every call here has already been verified as signed with its box's key. ChatGPT has no path to
these actions. Each action returns (HTTP status, reply for the box) and records its event.
"""

from __future__ import annotations

import secrets
from typing import Any

from mo import boxes, chats, events, profiles, runs, tunes
from mo.events import HUMAN_USER, MO


# Actions that only read, or report what the window saw. Allowed in any window, even an older one.
READ_ONLY = {"state", "list", "list_seeds", "list_tunes", "result", "tune_state", "recent", "followup"}


def stale(box: dict[str, Any]) -> bool:
    """A newer MO window is open in this window's chat: only the newest one is interactive."""
    newest = chats.latest(box.get("chat"))
    return newest is not None and newest != box["id"]


def handle(box: dict[str, Any], body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    action = body.get("action")
    handler = ACTIONS.get(box["kind"], {}).get(action) or EVERY_BOX.get(action)
    if handler is None:
        return refuse(box, action, f"{action!r} isn't an action for a {box['kind']} box")
    old = stale(box)
    if old and action not in READ_ONLY:
        return refuse(box, action, "A newer MO window is open in this chat. Use that one.", status=409)
    try:
        status, reply = handler(box, body)
    except ValueError as exc:
        return refuse(box, action, str(exc), status=400)
    return status, {**reply, "stale": old}


def refuse(box: dict[str, Any], action: Any, reason: str, status: int = 403) -> tuple[int, dict[str, Any]]:
    events.record(MO, "refused", box=box["id"], action=action, reason=reason)
    return status, {"error": reason}


# --- two-click confirmation (for anything permanent)

def _ask(box, what: str, name: str) -> str:
    """First click: remember what's being confirmed and issue a one-time code for it."""
    box["pending"] = {"what": what, "profile": name, "code": secrets.token_urlsafe(12)}
    boxes.save(box)
    return box["pending"]["code"]


def _confirmed(box, what: str, name: str, code: Any) -> None:
    """Second click: the code must match this box, this action, and this profile. Used once either way."""
    pending = box.pop("pending", None)
    boxes.save(box)
    if (not pending or pending["what"] != what or pending["profile"] != name
            or not secrets.compare_digest(pending["code"], str(code))):
        raise ValueError("Not confirmed; click the button again")


# --- every box: the chat's voice (AGENTS.md item 7). A box knows its chat from when it opened;
# the voice itself is read fresh, since the human user may change it from another box in the chat.

def _voice(box) -> str | None:
    return chats.voice(box.get("chat"))


def _state(box, body):
    return 200, {"voice": _voice(box), "profiles": [p["name"] for p in profiles.list_all()]}


def _set_voice(box, body):
    name = chats.set_voice(box.get("chat"), body.get("name"))
    events.record(HUMAN_USER, "voice_set", box=box["id"], profile=name, chat=box.get("chat"))
    return _state(box, body)


def _followup(box, body):
    """What the window saw when it posted a message to ChatGPT (sent, or the error). A fact for the
    trace: the one step MO can't see itself."""
    ok = body.get("ok") is True
    events.record(MO, "followup_sent" if ok else "followup_failed", box=box["id"], chat=box.get("chat"),
                  what=str(body.get("what", ""))[:80], reported_by="window",
                  **({} if ok else {"error": str(body.get("error", ""))[:200]}))
    return 200, {}


EVERY_BOX = {"state": _state, "set_voice": _set_voice, "followup": _followup}


# --- config box: Profiles tab

def _list(box, body):
    return 200, {"profiles": profiles.list_all(), "voice": _voice(box)}


def _create(box, body):
    created = profiles.create(body.get("name"))
    events.record(HUMAN_USER, "profile_created", box=box["id"], profile=created["name"])
    return 200, {"created": created, **_list(box, body)[1]}


def _delete(box, body):
    name = profiles.normalize(body.get("name"))
    if not profiles.exists(name):
        raise ValueError(f"No profile named {name!r}")
    code = _ask(box, "delete", name)
    events.record(HUMAN_USER, "profile_delete_requested", box=box["id"], profile=name)
    return 200, {"confirm": code, "will_lose": profiles.summary(name)}


def _confirm_delete(box, body):
    name = profiles.normalize(body.get("name"))
    _confirmed(box, "delete", name, body.get("confirm"))
    lost = profiles.delete(name)
    chats_cleared = chats.forget_profile(name)
    tunes.forget_profile(name)
    purged = events.purge_profile(name)
    # The tombstone names the profile in `deleted_profile`, not `profile`, so it stays in "All" and
    # never shows up under a new profile that reuses the name.
    events.record(HUMAN_USER, "profile_deleted", box=box["id"], deleted_profile=name,
                  lost={"seeds": lost["seeds"], "tunes": lost["tunes"], "events": purged, "chats": chats_cleared})
    return 200, {"deleted": lost, **_list(box, body)[1]}


def _clear_seeds(box, body):
    name = profiles.normalize(body.get("name"))
    if not profiles.exists(name):
        raise ValueError(f"No profile named {name!r}")
    code = _ask(box, "clear_seeds", name)
    events.record(HUMAN_USER, "seeds_clear_requested", box=box["id"], profile=name)
    return 200, {"confirm": code, "will_lose": profiles.summary(name)}


def _confirm_clear_seeds(box, body):
    name = profiles.normalize(body.get("name"))
    _confirmed(box, "clear_seeds", name, body.get("confirm"))
    removed = profiles.clear_seeds(name)
    events.record(HUMAN_USER, "seeds_cleared", box=box["id"], profile=name, seeds=removed)
    return 200, {"cleared": removed, **_list(box, body)[1]}


# --- config box: Seeds tab (works on the chat's voice)

def _need_voice(box) -> str:
    name = _voice(box)
    if not name:
        raise ValueError("Pick the voice for this chat first (Profiles tab)")
    return name


def _add_seed(box, body):
    name = _need_voice(box)
    seed = profiles.add_seed(name, profiles.plain_text(body.get("text")), box["id"])
    # The text lives only in the profile's store; the event keeps the id and size.
    events.record(HUMAN_USER, "seed_added", box=box["id"], profile=name, seed=seed["id"], words=seed["words"])
    return 200, {"saved": {"id": seed["id"], "words": seed["words"], "profile": name}}


def _list_seeds(box, body):
    name = _voice(box)
    return 200, {"profile": name, "seeds": profiles.seeds(name) if name else []}


def _delete_seeds(box, body):
    """No confirmation: the human user checked exactly which seeds to delete."""
    name = _need_voice(box)
    deleted = profiles.delete_seeds(name, body.get("ids"))
    events.record(HUMAN_USER, "seeds_deleted", box=box["id"], profile=name, seeds=deleted)
    return 200, {"deleted": deleted, **_list_seeds(box, body)[1]}


# --- output window

def _run(box, body=None) -> dict[str, Any]:
    """The window's run, or a rerun this window started (and nothing else)."""
    wanted = (body or {}).get("run")
    if wanted and wanted in box.get("reruns", []):
        return runs.find(wanted)
    return runs.find(box.get("run"))


def _result(box, body):
    return 200, {**runs.summary(_run(box, body)), **_state(box, body)[1]}


def _choose_voice(box, body):
    """First output in a chat: the human user picks the chat's voice; the waiting run takes it."""
    run = _run(box)
    name = chats.set_voice(box.get("chat"), body.get("name"))
    events.record(HUMAN_USER, "voice_set", box=box["id"], profile=name, chat=box.get("chat"))
    runs.assign(run, name)
    runs.touch(run)  # the window now asks ChatGPT to continue; wait for it to pick that up
    events.record(MO, "run_ready", run=run["id"], profile=name, chat=run.get("chat"))
    return 200, {"continue": run["id"], **_result(box, body)[1]}


def _continue_clicked(box, body):
    """The human user asked ChatGPT to pick a stalled run back up (the window posts the message)."""
    run = _run(box, body)
    runs.touch(run)  # the user's click restarts the stall clock
    events.record(HUMAN_USER, "continue_clicked", box=box["id"], profile=run["profile"], run=run["id"],
                  chat=run.get("chat"), voice_loaded=runs.voice_loaded(run))
    return 200, {"continue": run["id"]}


def _rerun(box, body):
    """The same initial again, in the chat's (new) voice. The window follows the new run too."""
    name = _need_voice(box)
    new = runs.rerun(_run(box), name)
    box.setdefault("reruns", []).append(new["id"])
    boxes.save(box)
    events.record(HUMAN_USER, "rerun", box=box["id"], profile=name, run=new["id"], chat=new.get("chat"),
                  from_run=box.get("run"))
    return 200, {"continue": new["id"]}


# --- config window: Tunes tab (the chat's voice), like seeds: check and delete, no confirmation

def _list_tunes(box, body):
    name = _voice(box)
    return 200, {"profile": name, "tunes": tunes.sealed_for(name) if name else []}


def _delete_tunes(box, body):
    name = _need_voice(box)
    deleted = tunes.delete(name, body.get("ids"))
    events.record(HUMAN_USER, "tunes_deleted", box=box["id"], profile=name, tunes=deleted)
    return 200, {"deleted": deleted, **_list_tunes(box, body)[1]}


# --- tuning (Output window's "Tune voice profile", and the @MO tune window)

WORK = "work"   # tells the window to post "work on MO tune …" so ChatGPT takes the next step


def _tune(box) -> dict[str, Any]:
    if not box.get("tune"):
        raise ValueError("No tune in this window yet")
    return tunes.find(box["tune"])


def _tune_event(box, tune, type_, **data):
    events.record(HUMAN_USER, type_, box=box["id"], profile=tune["profile"], tune=tune["id"],
                  chat=tune.get("chat"), **data)


def _tune_state(box, body):
    tune = tunes.find(box["tune"]) if box.get("tune") else None
    return 200, {**(tunes.summary(tune) if tune else {"tune": None}), **_state(box, body)[1]}


def _start_tune(box, body):
    """Output window: "Not satisfied? Tune voice profile" tunes this result, in the voice it was written in.
    If the chat already has an unfinished tune, it resumes that one instead (no duplicates)."""
    run = _run(box)
    if not runs.done(run):
        raise ValueError("Wait until the voice is fully loaded, then tune")
    unfinished = tunes.open_for_chat(run.get("chat"))
    if unfinished:
        box["tune"] = unfinished["id"]
        boxes.save(box)
        tunes.set_window(unfinished, box["id"])
        _tune_event(box, unfinished, "tune_resumed")
        return 200, {"resumed": True, **_tune_state(box, body)[1]}
    tune = tunes.start(run["profile"], run.get("chat"), runs.current(run), run=run["id"])
    box["tune"] = tune["id"]
    boxes.save(box)
    tunes.set_window(tune, box["id"])
    _tune_event(box, tune, "tune_started", from_run=run["id"])
    return _tune_state(box, body)


def _tune_paste(box, body):
    """@MO tune with no output to tune: the human user pastes the text (exact, never through ChatGPT)."""
    name = _need_voice(box)
    tune = tunes.start(name, box.get("chat"), profiles.plain_text(body.get("text")))
    box["tune"] = tune["id"]
    boxes.save(box)
    tunes.set_window(tune, box["id"])
    _tune_event(box, tune, "tune_started", from_paste=True)
    return _tune_state(box, body)


def _tune_select(box, body):
    """The user clicked the sentences to tune (first..last), with an optional note."""
    tune = _tune(box)
    tunes.select(tune, body.get("first"), body.get("last"), body.get("note"))
    _tune_event(box, tune, "tune_part_picked", how="clicked", words=len(tune["target"].split()))
    return 200, {WORK: tune["id"], **_tune_state(box, body)[1]}


def _tune_choose_for_me(box, body):
    """Choose for Me: MO picks the opening."""
    tune = _tune(box)
    tunes.choose_for_me(tune, body.get("note"))
    _tune_event(box, tune, "tune_part_picked", how="chosen by MO", words=len(tune["target"].split()))
    return 200, {WORK: tune["id"], **_tune_state(box, body)[1]}


def _tune_choose(box, body):
    tune = _tune(box)
    final = bool(body.get("final"))
    tunes.choose(tune, body.get("pick"), body.get("comment"), final)
    last = tune["rounds"][-1]
    # The comment's text lives only in the tune; the event records that there was one.
    _tune_event(box, tune, "tune_sealed" if final else "tune_round_answered", round=last["round"],
                pick=last["pick"], commented=bool(last.get("comment")), **({"rounds": tunes.answered(tune)} if final else {}))
    reply = _tune_state(box, body)[1]
    return 200, reply if final else {WORK: tune["id"], **reply}


def _tune_done(box, body):
    """✓ Done, keep it: seal the tune with the last pick."""
    tune = _tune(box)
    tunes.done(tune)
    _tune_event(box, tune, "tune_sealed", rounds=tunes.answered(tune), by="done")
    return _tune_state(box, body)


def _tune_start_over(box, body):
    """Drop the unfinished tune (nothing stored) and start a fresh one on the same text."""
    old = _tune(box)
    tunes.discard(old)
    _tune_event(box, old, "tune_discarded")
    tune = tunes.start(old["profile"], old.get("chat"), old["source"]["text"], run=old["source"].get("run"))
    box["tune"] = tune["id"]
    boxes.save(box)
    tunes.set_window(tune, box["id"])
    _tune_event(box, tune, "tune_started", restarted_from=old["id"])
    return _tune_state(box, body)


def _tune_continue(box, body):
    """Continue? The user's click restarts the stall clock and asks ChatGPT to pick it back up."""
    tune = _tune(box)
    tunes.touch(tune)
    _tune_event(box, tune, "tune_continue_clicked", status=tune["status"])
    return 200, {WORK: tune["id"]}


TUNE_ACTIONS = {"tune_state": _tune_state, "tune_select": _tune_select, "tune_choose_for_me": _tune_choose_for_me,
                "tune_choose": _tune_choose, "tune_done": _tune_done,
                "tune_start_over": _tune_start_over, "tune_continue": _tune_continue}


# --- trace window: this chat's recent activity (read-only)

def _recent(box, body):
    """The last 15 events from this window's chat, ids and counts only (the full trace page has text)."""
    found = [e for e in events.read() if box.get("chat") and e.get("chat") == box["chat"]][-15:]
    keep = ("at", "actor", "type", "tool", "profile", "round", "pick", "pass_number", "words", "reason")
    return 200, {"events": [{k: e[k] for k in keep if k in e} for e in found]}


ACTIONS = {
    "trace": {"recent": _recent},
    "output": {"result": _result, "choose_voice": _choose_voice, "continue_clicked": _continue_clicked,
               "rerun": _rerun, "start_tune": _start_tune, **TUNE_ACTIONS},
    "tune": {"tune_paste": _tune_paste, **TUNE_ACTIONS},
    "config": {"list": _list, "create": _create, "delete": _delete, "confirm_delete": _confirm_delete,
               "clear_seeds": _clear_seeds, "confirm_clear_seeds": _confirm_clear_seeds,
               "add_seed": _add_seed, "list_seeds": _list_seeds, "delete_seeds": _delete_seeds,
               "list_tunes": _list_tunes, "delete_tunes": _delete_tunes},
}
